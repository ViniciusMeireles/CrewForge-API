from django.utils.translation import gettext_lazy as _

from apps.generics.mixins.views import FilterOptionsMixin, FormOptionsMixin
from apps.generics.utils.filters import orderable_filter_factory
from apps.generics.utils.schema import extend_schema_model_view_set
from apps.accounts.mixins.views import ModelViewSetMixin, OrganizationScopedViewSetMixin
from rest_framework import viewsets, backends

from apps.{app}.models.{resource} import {Resource}
from apps.{app}.serializers.{resource} import {Resource}Serializer
from apps.{app}.permissions import {Resource}Permission
from apps.{app}.filters import {Resource}Filter


@extend_schema_model_view_set(model={Resource})
class {Resource}ViewSet(
    OrganizationScopedViewSetMixin,
    FormOptionsMixin,
    FilterOptionsMixin,
    ModelViewSetMixin,
    viewsets.ModelViewSet,
):
    serializer_class = {Resource}Serializer
    queryset = {Resource}.objects.all()
    http_method_names = ['get', 'post', 'put', 'patch', 'delete']
    permission_classes = [{Resource}Permission]
    filterset_class = orderable_filter_factory({Resource}Serializer, {Resource}Filter)
    filter_backends = [backends.DjangoFilterBackend]
    base_filters = {'is_active': True}
