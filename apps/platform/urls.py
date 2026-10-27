from django.urls import include, path
from rest_framework import routers

from apps.platform.views import (
    ImpersonationExitView,
    PlatformAuditEventViewSet,
    PlatformOrganizationViewSet,
    PlatformOverviewView,
    PlatformUserViewSet,
)

app_name = 'platform'

router = routers.DefaultRouter()
router.register(r'organizations', PlatformOrganizationViewSet, basename='organizations')
router.register(r'users', PlatformUserViewSet, basename='users')
router.register(r'audit-events', PlatformAuditEventViewSet, basename='audit_events')

urlpatterns = [
    path('api/platform/overview/', PlatformOverviewView.as_view(), name='overview'),
    path(
        'api/platform/impersonation/exit/',
        ImpersonationExitView.as_view(),
        name='impersonation-exit',
    ),
    path('api/platform/', include(router.urls)),
]
