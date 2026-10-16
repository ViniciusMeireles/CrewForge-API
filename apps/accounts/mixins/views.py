from contextlib import contextmanager

from django.db import transaction

from apps.accounts.mixins.requests import OrganizationScopedRequestMixin
from apps.accounts.serializers.options import (
    OptionsOrganizationFilterSetSerializer,
    OptionsOrganizationModelSerializer,
)
from apps.accounts.utils.files import file_too_large_error, max_upload_request_size
from apps.audit.services import (
    diff_instance,
    label_for,
    record_audit_event,
    snapshot_instance,
)
from apps.generics.mixins.views import (
    OptionsModelMixin,
    OptionsModelViewSetMetaclass,
    OrderableModelViewSetMetaclass,
)


class ModelViewSetMetaclass(
    OptionsModelViewSetMetaclass,
    OrderableModelViewSetMetaclass,
):
    """
    Combine the orderable filter and options metaclasses.

    ``OptionsModelViewSetMetaclass`` comes first so ``OrderableModelViewSetMetaclass``
    runs inside its ``super().__new__``: the ``order_by`` filter already exists when
    the filter options are built.
    """


class OptionsOrganizationModelMixin(OptionsModelMixin):
    """Options mixin with organization and active scoping on relations."""

    options_serializer_class = OptionsOrganizationModelSerializer
    options_filterset_serializer_class = OptionsOrganizationFilterSetSerializer


class ModelViewSetMixin(
    OptionsOrganizationModelMixin,
    OrganizationScopedRequestMixin,
    metaclass=ModelViewSetMetaclass,
):
    """Mixin for views to add user, member, and organization properties."""

    audit_actions: dict[str, str] = {}
    audit_exclude_fields: tuple[str, ...] = ()

    def get_audit_action(self) -> str | None:
        return self.audit_actions.get(self.action)

    def get_audit_organization_id(self, instance) -> int | None:
        return getattr(instance, 'organization_id', None) or self.auth_organization_id

    @contextmanager
    def audited(self):
        """Run a write and its audit event in one transaction."""
        if not (action := self.get_audit_action()):
            yield None
            return
        with transaction.atomic():
            yield action

    def get_audit_kwargs(self, instance) -> dict:
        """Extra ``record_audit_event`` arguments (e.g. an explicit actor)."""
        return {}

    def record_audit(self, action: str, instance, changes=(), **kwargs) -> None:
        record_audit_event(
            action,
            request=self.request,
            organization_id=self.get_audit_organization_id(instance),
            target=instance,
            changes=changes,
            **self.get_audit_kwargs(instance),
            **kwargs,
        )

    def perform_create(self, serializer):
        with self.audited() as action:
            super().perform_create(serializer)
            if action:
                instance = serializer.instance
                changes = diff_instance({}, instance, self.audit_exclude_fields)
                self.record_audit(action, instance, changes)

    def perform_update(self, serializer):
        with self.audited() as action:
            before = snapshot_instance(serializer.instance, self.audit_exclude_fields)
            super().perform_update(serializer)
            if action:
                instance = serializer.instance
                changes = diff_instance(before, instance, self.audit_exclude_fields)
                if changes:
                    self.record_audit(action, instance, changes)

    def perform_destroy(self, instance):
        with self.audited() as action:
            target = {'target_id': instance.pk, 'target_label': label_for(instance)}
            if hasattr(instance, 'is_active'):
                instance.inactivate()
            else:
                super().perform_destroy(instance)
            if action:
                self.record_audit(action, instance, **target)


class OrganizationScopedViewSetMixin(OrganizationScopedRequestMixin):
    organization_filter = 'organization_id'
    base_filters = {}

    def get_base_queryset_filters(self) -> dict:
        return dict(self.base_filters)

    def get_organization_filter_kwargs(self) -> dict:
        return {self.organization_filter: self.auth_organization_id}

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                **self.get_organization_filter_kwargs(),
                **self.get_base_queryset_filters(),
            )
        )


class UploadSizeLimitMixin:
    upload_error_path = ('file',)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        try:
            content_length = int(request.META.get('CONTENT_LENGTH') or 0)
        except ValueError:
            content_length = 0
        if content_length > max_upload_request_size():
            raise file_too_large_error(path=self.upload_error_path)
