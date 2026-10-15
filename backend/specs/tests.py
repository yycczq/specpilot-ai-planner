import json
import os
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import DatabaseError, IntegrityError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import Spec


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "tests"}})
class SpecApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_health(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["database"], "ok")

    @patch("specs.views.connection.cursor", side_effect=DatabaseError("database offline"))
    def test_health_reports_database_failure(self, _cursor):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["status"], "degraded")
        self.assertEqual(response.data["database"], "unavailable")

    def test_register_login_current_user_and_logout(self):
        registration = self.client.post(
            "/api/auth/register/",
            {"username": "alice", "email": "alice@example.com", "password": "GoodHorse!2026"},
            format="json",
        )
        self.assertEqual(registration.status_code, 201)
        self.assertEqual(registration.data["user"]["username"], "alice")
        self.assertNotIn("password", registration.data["user"])
        user = get_user_model().objects.get(username="alice")
        self.assertTrue(user.check_password("GoodHorse!2026"))
        self.assertEqual(registration.data["token"], Token.objects.get(user=user).key)

        login = self.client.post(
            "/api/auth/login/",
            {"username": "ALICE@example.com", "password": "GoodHorse!2026"},
            format="json",
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.data["token"], registration.data["token"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {login.data['token']}")
        current_user = self.client.get("/api/auth/me/")
        self.assertEqual(current_user.status_code, 200)
        self.assertEqual(current_user.data["email"], "alice@example.com")
        logout = self.client.post("/api/auth/logout/")
        self.assertEqual(logout.status_code, 204)
        self.client.credentials()
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_expired_token_is_revoked_and_login_issues_a_fresh_one(self):
        user = get_user_model().objects.create_user(
            username="alice", email="alice@example.com", password="GoodHorse!2026"
        )
        token = Token.objects.create(user=user)
        old_key = token.key
        Token.objects.filter(pk=token.pk).update(created=timezone.now() - timedelta(days=31))

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {old_key}")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        self.assertFalse(Token.objects.filter(user=user).exists())

        self.client.credentials()
        login = self.client.post(
            "/api/auth/login/", {"username": "alice", "password": "GoodHorse!2026"}, format="json"
        )
        self.assertEqual(login.status_code, 200)
        self.assertNotEqual(login.data["token"], old_key)

    def test_registration_rejects_duplicate_account_and_weak_password(self):
        data = {"username": "alice", "email": "alice@example.com", "password": "GoodHorse!2026"}
        first = self.client.post("/api/auth/register/", data, format="json")
        duplicate = self.client.post(
            "/api/auth/register/",
            {**data, "username": "alice2", "email": "ALICE@example.com"},
            format="json",
        )
        weak = self.client.post(
            "/api/auth/register/",
            {"username": "bob", "email": "bob@example.com", "password": "12345678"},
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(weak.status_code, 400)
        self.assertEqual(get_user_model().objects.count(), 1)

    @patch("specs.views.RegistrationSerializer.save", side_effect=IntegrityError("username race"))
    def test_registration_reports_a_database_uniqueness_race_as_client_error(self, _save):
        response = self.client.post(
            "/api/auth/register/",
            {"username": "alice", "email": "alice@example.com", "password": "GoodHorse!2026"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(get_user_model().objects.count(), 0)

    @override_settings(DEMO_ALLOW_ANONYMOUS=False)
    def test_anonymous_demo_can_be_disabled_without_disabling_health_or_registration(self):
        self.assertEqual(self.client.get("/api/health/").status_code, 200)
        self.assertEqual(self.client.get("/api/specs/").status_code, 401)
        self.assertEqual(self.client.get("/api/overview/").status_code, 401)
        self.assertEqual(
            self.client.post("/api/auth/register/", {
                "username": "alice",
                "email": "alice@example.com",
                "password": "GoodHorse!2026",
            }, format="json").status_code,
            201,
        )

    @patch.dict(os.environ, {"AI_PROVIDER": "mock"})
    def test_invalid_review_status_does_not_create_a_revision(self):
        created = self.client.post("/api/specs/", {"requirement": "用户可以创建并跟踪一个需求"}, format="json")
        response = self.client.patch(
            f"/api/specs/{created.data['id']}/",
            {"result": {"title": "有效标题"}, "status": "published"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Spec.objects.get(id=created.data["id"]).revisions.count(), 0)

    @patch.dict(os.environ, {"AI_PROVIDER": "mock"})
    def test_oversized_review_result_does_not_create_a_revision(self):
        created = self.client.post("/api/specs/", {"requirement": "用户可以创建并跟踪一个需求"}, format="json")
        response = self.client.patch(
            f"/api/specs/{created.data['id']}/",
            {"result": {"title": "需求标题", "summary": "x" * 2_000_001}},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Spec.objects.get(id=created.data["id"]).revisions.count(), 0)

    @patch.dict(os.environ, {"AI_PROVIDER": "mock"})
    def test_api_rejects_non_object_bodies_without_server_errors(self):
        created = self.client.post("/api/specs/", {"requirement": "用户可以创建并跟踪一个需求"}, format="json")
        spec_id = created.data["id"]
        response = self.client.post("/api/specs/", ["not", "an", "object"], format="json")
        edited = self.client.patch(f"/api/specs/{spec_id}/", ["not", "an", "object"], format="json")
        provider = self.client.post("/api/providers/test/", ["not", "an", "object"], format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(edited.status_code, 400)
        self.assertEqual(provider.status_code, 400)

    @patch("rest_framework.throttling.ScopedRateThrottle.THROTTLE_RATES", {"spec_create": "1/hour"})
    @patch.dict(os.environ, {"AI_PROVIDER": "mock"})
    def test_spec_generation_is_rate_limited(self):
        cache.clear()
        first = self.client.post("/api/specs/", {"requirement": "用户可以创建并跟踪一个需求"}, format="json")
        second = self.client.post("/api/specs/", {"requirement": "用户可以创建并跟踪另一个需求"}, format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 429)

    @patch(
        "rest_framework.throttling.ScopedRateThrottle.THROTTLE_RATES",
        {"spec_create": "30/hour", "spec_update": "1/hour"},
    )
    @patch.dict(os.environ, {"AI_PROVIDER": "mock"})
    def test_spec_updates_are_rate_limited(self):
        cache.clear()
        created = self.client.post("/api/specs/", {"requirement": "用户可以创建并跟踪一个需求"}, format="json")
        spec_url = f"/api/specs/{created.data['id']}/"
        payload = {"result": {"title": "需求标题", "summary": "新的需求摘要"}}
        first = self.client.patch(spec_url, payload, format="json")
        second = self.client.patch(spec_url, payload, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)

    @patch("specs.services._call_anthropic")
    @patch.dict(os.environ, {"AI_PROVIDER": "anthropic"})
    def test_default_provider_cache_is_scoped_to_account(self, call_provider):
        from .services import analyze_requirement

        cache.clear()
        call_provider.return_value = {"title": "需求", "summary": "摘要"}
        requirement = "同一个需求，但属于不同账号的数据"
        analyze_requirement(requirement, cache_scope="alice")
        analyze_requirement(requirement, cache_scope="alice")
        analyze_requirement(requirement, cache_scope="bob")
        self.assertEqual(call_provider.call_count, 2)

    def test_model_json_is_schema_checked_and_extra_fields_are_discarded(self):
        from .services import AIProviderError, _extract_json

        payload = {
            "title": "需求标题",
            "summary": "需求摘要",
            "recommendation": "建议先做一个核心流程并小范围验证。",
            "mvp_scope": {"in_scope": ["主流程"], "out_of_scope": ["高级报表"]},
            "implementation_plan": [{"phase": "验证", "objective": "验证主流程", "tasks": ["访谈用户"], "deliverable": "试用记录"}],
            "success_metrics": [{"name": "任务完成率", "definition": "完成数除以开始数", "target": "先建立基线", "internal_note": "discard me"}],
            "assumptions": ["首版聚焦一个核心场景"],
            "questions": [],
            "user_stories": [],
            "acceptance_criteria": [],
            "api_endpoints": [{"method": "GET", "path": "/items", "purpose": "读取列表"}],
            "test_cases": [{"name": "正常输入", "steps": "提交输入", "expected": "成功"}],
            "risks": [],
            "unexpected_secret": "do not persist",
        }
        parsed = _extract_json(json.dumps(payload, ensure_ascii=False))
        self.assertNotIn("unexpected_secret", parsed)
        self.assertNotIn("internal_note", parsed["success_metrics"][0])
        payload["test_cases"] = ["bad item"]
        with self.assertRaises(AIProviderError):
            _extract_json(json.dumps(payload, ensure_ascii=False))
        payload["test_cases"] = [{"name": "有效输入", "steps": "提交", "expected": "成功"}]
        payload["implementation_plan"][0]["tasks"] = "bad tasks"
        with self.assertRaises(AIProviderError):
            _extract_json(json.dumps(payload, ensure_ascii=False))

    def test_mock_result_contains_a_concrete_plan_without_invented_targets(self):
        from .services import _mock_result

        result = _mock_result("给玩家做一个游戏内反馈入口，让他们能提交问题并查看处理状态")
        self.assertIn("游戏内反馈入口", result["recommendation"])
        self.assertTrue(result["mvp_scope"]["in_scope"])
        self.assertGreaterEqual(len(result["implementation_plan"]), 3)
        self.assertTrue(all(phase["tasks"] and phase["deliverable"] for phase in result["implementation_plan"]))
        self.assertEqual(result["success_metrics"][0]["target"], "先建立基线，再由团队设定目标")

    @patch.dict(os.environ, {"AI_PROVIDER": "mock"})
    def test_authenticated_specs_and_revisions_are_isolated_per_user(self):
        user_model = get_user_model()
        alice = user_model.objects.create_user(username="alice", password="GoodHorse!2026")
        bob = user_model.objects.create_user(username="bob", password="GoodHorse!2026")
        alice_token = Token.objects.create(user=alice)
        bob_token = Token.objects.create(user=bob)

        alice_client = APIClient()
        alice_client.credentials(HTTP_AUTHORIZATION=f"Token {alice_token.key}")
        created = alice_client.post(
            "/api/specs/", {"requirement": "用户可以创建并跟踪一个自己的需求"}, format="json"
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(Spec.objects.get(id=created.data["id"]).owner, alice)

        bob_client = APIClient()
        bob_client.credentials(HTTP_AUTHORIZATION=f"Token {bob_token.key}")
        self.assertEqual(bob_client.get("/api/specs/").data, [])
        self.assertEqual(bob_client.get("/api/overview/").data["total"], 0)
        self.assertEqual(bob_client.get(f"/api/specs/{created.data['id']}/").status_code, 404)
        self.assertEqual(bob_client.get(f"/api/specs/{created.data['id']}/revisions/").status_code, 404)

        anonymous = APIClient()
        self.assertEqual(anonymous.get("/api/specs/").data, [])

    @patch.dict(os.environ, {"AI_PROVIDER": "mock"})
    def test_anonymous_demo_data_is_separate_from_signed_in_users(self):
        anonymous_spec = self.client.post(
            "/api/specs/", {"requirement": "访客可以创建一份演示需求草案"}, format="json"
        )
        user = get_user_model().objects.create_user(username="alice", password="GoodHorse!2026")
        token = Token.objects.create(user=user)
        signed_in = APIClient()
        signed_in.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        private_spec = signed_in.post(
            "/api/specs/", {"requirement": "登录用户可以创建一份私有需求草案"}, format="json"
        )

        self.assertEqual(anonymous_spec.status_code, 201)
        self.assertEqual(private_spec.status_code, 201)
        self.assertEqual(len(self.client.get("/api/specs/").data), 1)
        self.assertEqual(len(signed_in.get("/api/specs/").data), 1)
        self.assertNotEqual(anonymous_spec.data["id"], private_spec.data["id"])

    def test_rejects_short_requirements(self):
        response = self.client.post("/api/specs/", {"requirement": "做页面"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Spec.objects.count(), 0)

    @patch.dict(os.environ, {"AI_PROVIDER": "mock"})
    def test_creates_and_lists_a_spec(self):
        response = self.client.post(
            "/api/specs/", {"requirement": "玩家可以提交游戏内的道具问题，并查看处理进度"}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "draft")
        self.assertTrue(response.data["result"]["acceptance_criteria"])
        listed = self.client.get("/api/specs/")
        self.assertEqual(len(listed.data), 1)

    @patch.dict(os.environ, {"AI_PROVIDER": "mock"})
    def test_spec_list_supports_bounded_offset_pagination(self):
        first = self.client.post("/api/specs/", {"requirement": "第一份需求应该可以被列表查询"}, format="json")
        second = self.client.post("/api/specs/", {"requirement": "第二份需求应该可以被列表查询"}, format="json")
        Spec.objects.filter(id=first.data["id"]).update(updated_at=timezone.now() - timedelta(minutes=1))
        Spec.objects.filter(id=second.data["id"]).update(updated_at=timezone.now())
        first_page = self.client.get("/api/specs/?limit=1&offset=0")
        second_page = self.client.get("/api/specs/?limit=1&offset=1")
        invalid = self.client.get("/api/specs/?limit=1000&offset=-1")
        expected_page_id = list(Spec.objects.order_by("-updated_at", "-id").values_list("id", flat=True))[1]
        self.assertEqual(len(first_page.data), 1)
        self.assertEqual(first_page["X-Total-Count"], "2")
        self.assertEqual(first_page["X-Next-Offset"], "1")
        self.assertEqual(len(second_page.data), 1)
        self.assertEqual(second_page.data[0]["id"], str(expected_page_id))
        self.assertNotIn("X-Next-Offset", second_page)
        self.assertEqual(invalid.status_code, 400)

    @patch.dict(os.environ, {"AI_PROVIDER": "mock"})
    def test_manual_review_saves_a_revision(self):
        created = self.client.post("/api/specs/", {"requirement": "用户可以创建并跟踪一个需求"}, format="json")
        spec_id = created.data["id"]
        edited = dict(created.data["result"])
        edited["summary"] = "经过本人审阅后的说明"
        response = self.client.patch(
            f"/api/specs/{spec_id}/", {"result": edited, "status": "reviewed"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "reviewed")
        revisions = self.client.get(f"/api/specs/{spec_id}/revisions/")
        self.assertEqual(len(revisions.data), 1)
        self.assertNotEqual(revisions.data[0]["result"]["summary"], "经过本人审阅后的说明")

    @patch("specs.views.analyze_requirement")
    def test_byok_spec_generation_does_not_return_the_api_key(self, analyze):
        analyze.return_value = {
            "title": "需求标题",
            "summary": "需求摘要",
            "recommendation": "建议先实现主流程。",
            "mvp_scope": {"in_scope": [], "out_of_scope": []},
            "implementation_plan": [],
            "success_metrics": [],
            "assumptions": [],
            "questions": [],
            "user_stories": [],
            "acceptance_criteria": [],
            "api_endpoints": [],
            "test_cases": [],
            "risks": [],
            "mode": "openai-compatible",
        }
        provider = {
            "base_url": "https://api.example.com/v1",
            "model": "example-model",
            "api_key": "secret-test-key",
        }
        response = self.client.post(
            "/api/specs/", {"requirement": "用户可以创建并跟踪一个需求", "provider": provider}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("secret-test-key", str(response.data))
        self.assertNotIn("secret-test-key", str(Spec.objects.get(id=response.data["id"]).result))
        analyze.assert_called_once_with(
            "用户可以创建并跟踪一个需求", user_provider=provider, cache_scope="anonymous"
        )

    @patch("specs.views.test_openai_compatible")
    def test_provider_test_returns_only_safe_status(self, test_provider):
        test_provider.return_value = {"status": "ok", "provider": "openai-compatible"}
        response = self.client.post(
            "/api/providers/test/",
            {"provider": {"base_url": "https://api.example.com/v1", "model": "demo", "api_key": "do-not-return"}},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"status": "ok", "provider": "openai-compatible"})
        self.assertNotIn("do-not-return", str(response.data))

    def test_byok_rejects_private_network_addresses(self):
        from .services import AIProviderError, _provider_config

        with self.assertRaises(AIProviderError):
            _provider_config({"base_url": "http://127.0.0.1:8000/v1", "model": "demo", "api_key": "secret"})

    def test_byok_localhost_is_disabled_outside_development_configuration(self):
        from .services import AIProviderError, _provider_config

        provider = {"base_url": "http://localhost:9000/v1", "model": "demo", "api_key": "secret"}
        with override_settings(ALLOW_LOCAL_BYOK=True):
            self.assertEqual(_provider_config(provider)["host"], "localhost")
        with override_settings(ALLOW_LOCAL_BYOK=False):
            with self.assertRaises(AIProviderError):
                _provider_config(provider)

    @patch("specs.services._PinnedHTTPSConnection")
    @patch("specs.services._provider_config")
    def test_openai_compatible_request_uses_caller_model_and_key(self, provider_config, connection_factory):
        from .services import _compatible_chat

        provider_config.return_value = {
            "host": "api.example.com",
            "host_header": "api.example.com",
            "port": 443,
            "scheme": "https",
            "path": "/v1/chat/completions",
            "addresses": ["203.0.113.10"],
            "model": "caller-model",
            "api_key": "caller-secret",
        }
        connection = connection_factory.return_value
        response = connection.getresponse.return_value
        response.status = 200
        response.read.return_value = b'{"choices":[{"message":{"content":"OK"}}]}'

        content = _compatible_chat({"provider": "settings"}, [{"role": "user", "content": "test"}], 16)

        self.assertEqual(content, "OK")
        request_args, request_kwargs = connection.request.call_args
        self.assertEqual(request_args, ("POST", "/v1/chat/completions"))
        self.assertEqual(request_kwargs["headers"]["Authorization"], "Bearer caller-secret")
        self.assertEqual(json.loads(request_kwargs["body"])["model"], "caller-model")
