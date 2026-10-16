from django.urls import include, path
from rest_framework import routers

from apps.audit.views.audit_event import AuditEventViewSet

app_name = 'audit'


router = routers.DefaultRouter()
router.register(r'events', AuditEventViewSet, basename='audit_events')


urlpatterns = [
    path('api/audit/', include(router.urls)),
]
