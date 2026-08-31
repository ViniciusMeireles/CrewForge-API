from django.urls import include, path
from rest_framework import routers

from apps.{app}.viewsets.{resource} import {Resource}ViewSet

app_name = '{app}'

router = routers.DefaultRouter()
router.register(r'{url_segment}', {Resource}ViewSet, basename='{basename}')

urlpatterns = [
    path('api/{url_segment}/', include(router.urls)),
]
