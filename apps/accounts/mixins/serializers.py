from apps.accounts.mixins.fields import (
    OrganizationScopedFieldMixin,
    PrimaryKeyRelatedField,
)


class ModelSerializerMixin(OrganizationScopedFieldMixin):
    """
    Mixin for ModelSerializer to add user, member, and organization properties.
    """

    serializer_related_field = PrimaryKeyRelatedField
    _default_read_only_fields = [
        'id',
        'is_active',
        'created_at',
        'updated_at',
        'created_by',
        'updated_by',
    ]

    @property
    def validated_data(self):
        data = dict()
        concrete_fields = [f.attname for f in self.Meta.model._meta.concrete_fields]
        if 'created_by_id' in concrete_fields and not self.instance:
            data.update({'created_by': self.auth_user})
        if 'updated_by_id' in concrete_fields:
            data.update({'updated_by': self.auth_user})
        if 'organization_id' in concrete_fields and not self.instance:
            data.update({'organization': self.auth_organization})

        data.update(super().validated_data)
        return data
