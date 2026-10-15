import json
import os

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import get_or_issue_token
from .models import Spec, SpecRevision
from .serializers import LoginSerializer, RegistrationSerializer, SpecRevisionSerializer, SpecSerializer, UserSerializer
from .services import AIProviderError, analyze_requirement, test_openai_compatible

User = get_user_model()


class DemoOrAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return bool(getattr(request.user, "is_authenticated", False)) or settings.DEMO_ALLOW_ANONYMOUS


def visible_specs(request):
    """Keep signed-in records private while preserving the anonymous demo mode."""
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return Spec.objects.filter(owner=user)
    return Spec.objects.filter(owner__isnull=True)


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "auth_register"

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = serializer.save()
                token = get_or_issue_token(user)
        except IntegrityError:
            return Response(
                {"detail": "用户名或邮箱已被注册，请换一个再试。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {"token": token.key, "user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "auth_login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data["username"]
        password = serializer.validated_data["password"]
        username = identifier
        if "@" in identifier:
            username = (
                User.objects.filter(email__iexact=identifier)
                .values_list("username", flat=True)
                .first()
                or identifier
            )
        user = authenticate(request=request, username=username, password=password)
        if user is None:
            return Response({"detail": "用户名、邮箱或密码不正确。"}, status=status.HTTP_401_UNAUTHORIZED)
        token = get_or_issue_token(user)
        return Response({"token": token.key, "user": UserSerializer(user).data})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.auth.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except DatabaseError:
            return Response(
                {"status": "degraded", "service": "specpilot-api", "database": "unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            {
                "status": "ok",
                "service": "specpilot-api",
                "database": "ok",
                "ai_provider": os.getenv("AI_PROVIDER", "mock"),
            }
        )


class OverviewView(APIView):
    permission_classes = [DemoOrAuthenticated]

    def get(self, request):
        specs = visible_specs(request)
        return Response(
            {
                "total": specs.count(),
                "drafts": specs.filter(status=Spec.Status.DRAFT).count(),
                "reviewed": specs.filter(status=Spec.Status.REVIEWED).count(),
            }
        )


class SpecListCreateView(APIView):
    permission_classes = [DemoOrAuthenticated]

    def get_throttles(self):
        if self.request.method == "POST":
            self.throttle_scope = "spec_create"
        return super().get_throttles()

    def get(self, request):
        specs = visible_specs(request).annotate(revision_count=Count("revisions")).order_by("-updated_at", "-id")
        query = request.query_params.get("q", "").strip()
        if len(query) > 100:
            return Response({"detail": "搜索词不能超过 100 个字符。"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            limit = int(request.query_params.get("limit", 50))
            offset = int(request.query_params.get("offset", 0))
        except (TypeError, ValueError):
            return Response({"detail": "limit 和 offset 必须是整数。"}, status=status.HTTP_400_BAD_REQUEST)
        if not 1 <= limit <= 50 or not 0 <= offset <= 1_000_000:
            return Response(
                {"detail": "limit 必须在 1 到 50 之间，offset 必须在 0 到 1000000 之间。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if query:
            specs = specs.filter(Q(requirement__icontains=query) | Q(result__title__icontains=query))
        total = specs.count()
        page = list(specs[offset : offset + limit])
        response = Response(SpecSerializer(page, many=True).data)
        response["X-Total-Count"] = str(total)
        if offset + len(page) < total:
            response["X-Next-Offset"] = str(offset + len(page))
        return response

    def post(self, request):
        if not isinstance(request.data, dict):
            return Response({"detail": "请求内容必须是 JSON 对象。"}, status=status.HTTP_400_BAD_REQUEST)
        requirement = request.data.get("requirement", "")
        if not isinstance(requirement, str) or len(requirement.strip()) < 8:
            return Response({"detail": "请至少输入 8 个字符的需求描述。"}, status=status.HTTP_400_BAD_REQUEST)
        if len(requirement) > 5000:
            return Response({"detail": "需求描述不能超过 5000 个字符。"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = getattr(request, "user", None)
            cache_scope = str(user.pk) if user is not None and user.is_authenticated else "anonymous"
            result = analyze_requirement(
                requirement.strip(), user_provider=request.data.get("provider"), cache_scope=cache_scope
            )
        except AIProviderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        owner = request.user if getattr(request.user, "is_authenticated", False) else None
        spec = Spec.objects.create(owner=owner, requirement=requirement.strip(), result=result)
        spec.revision_count = 0
        return Response(SpecSerializer(spec).data, status=status.HTTP_201_CREATED)


class SpecDetailView(APIView):
    permission_classes = [DemoOrAuthenticated]

    def get_throttles(self):
        if self.request.method == "PATCH":
            self.throttle_scope = "spec_update"
        return super().get_throttles()

    def get(self, request, spec_id):
        spec = get_object_or_404(visible_specs(request).annotate(revision_count=Count("revisions")), id=spec_id)
        return Response(SpecSerializer(spec).data)

    @transaction.atomic
    def patch(self, request, spec_id):
        if not isinstance(request.data, dict):
            return Response({"detail": "请求内容必须是 JSON 对象。"}, status=status.HTTP_400_BAD_REQUEST)
        spec = get_object_or_404(visible_specs(request).select_for_update(), id=spec_id)
        new_result = request.data.get("result")
        valid_title = isinstance(new_result, dict) and isinstance(new_result.get("title"), str)
        if not valid_title or not new_result["title"].strip():
            return Response({"detail": "请提交包含标题的需求结果对象。"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result_bytes = json.dumps(
                new_result,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError):
            return Response({"detail": "需求结果必须是有效的 JSON 数据。"}, status=status.HTTP_400_BAD_REQUEST)
        if len(result_bytes) > 2_000_000:
            return Response({"detail": "需求结果不能超过 2 MB。"}, status=status.HTTP_400_BAD_REQUEST)
        new_status = request.data.get("status", spec.status)
        if new_status not in Spec.Status.values:
            return Response({"detail": "状态只能是 draft 或 reviewed。"}, status=status.HTTP_400_BAD_REQUEST)
        SpecRevision.objects.create(spec=spec, result=spec.result, note="修改前快照")
        spec.result = new_result
        spec.status = new_status
        spec.save(update_fields=["result", "status", "updated_at"])
        spec.revision_count = spec.revisions.count()
        return Response(SpecSerializer(spec).data)


class SpecRevisionListView(APIView):
    permission_classes = [DemoOrAuthenticated]

    def get(self, request, spec_id):
        spec = get_object_or_404(visible_specs(request), id=spec_id)
        return Response(SpecRevisionSerializer(spec.revisions.all(), many=True).data)


class ProviderTestView(APIView):
    """Check one caller-owned OpenAI-compatible API config without saving its secret."""
    permission_classes = [DemoOrAuthenticated]
    throttle_scope = "provider_test"

    def post(self, request):
        if not isinstance(request.data, dict):
            return Response({"detail": "请求内容必须是 JSON 对象。"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = test_openai_compatible(request.data.get("provider"))
        except AIProviderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)
