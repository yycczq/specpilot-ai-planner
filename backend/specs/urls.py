from django.urls import path

from .views import (
    CurrentUserView,
    HealthView,
    LoginView,
    LogoutView,
    OverviewView,
    ProviderTestView,
    RegisterView,
    SpecDetailView,
    SpecListCreateView,
    SpecRevisionListView,
)


urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", CurrentUserView.as_view(), name="auth-me"),
    path("overview/", OverviewView.as_view(), name="overview"),
    path("specs/", SpecListCreateView.as_view(), name="spec-list-create"),
    path("specs/<uuid:spec_id>/", SpecDetailView.as_view(), name="spec-detail"),
    path("specs/<uuid:spec_id>/revisions/", SpecRevisionListView.as_view(), name="spec-revisions"),
    path("providers/test/", ProviderTestView.as_view(), name="provider-test"),
]
