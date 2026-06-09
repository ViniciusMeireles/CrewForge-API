from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.mixins.serializers import ModelSerializerMixin
from apps.accounts.models.member import Member
from apps.accounts.models.organization import Organization
from apps.accounts.serializers.mixins import UserTokenSerializerMixin
from apps.accounts.serializers.organization import OrganizationSerializer
from apps.accounts.serializers.user import UserSerializer

User = get_user_model()


class SignupSerializer(
    UserTokenSerializerMixin, ModelSerializerMixin, serializers.ModelSerializer
):
    # Serialized fields
    user = UserSerializer()
    organization = OrganizationSerializer()

    class Meta:
        model = Member
        fields = '__all__'
        read_only_fields = ModelSerializerMixin._default_read_only_fields + ['role']

    @property
    def validated_data(self):
        data = super().validated_data
        data.setdefault('role', MemberRoleChoices.OWNER)
        return data

    @classmethod
    def _create_user(cls, user_data):
        """Create a user instance."""
        user = User(**user_data)
        user.set_password(user_data.get('password'))
        user.save()
        user.created_by = user
        user.updated_by = user
        user.save(update_fields=['created_by', 'updated_by'])
        return user

    def create(self, validated_data):
        with transaction.atomic():
            user_data = validated_data.pop('user')
            organization_data = validated_data.pop('organization')

            user = self._create_user(user_data)
            self.set_tokens_for_user(user)

            organization = Organization.objects.create(
                created_by=user,
                updated_by=user,
                **organization_data,
            )
            validated_data.update(
                {
                    'user': user,
                    'organization': organization,
                    'created_by': user,
                    'updated_by': user,
                }
            )
            instance = super().create(validated_data)
            organization.owner = instance
            organization.save(update_fields=['owner'])
        return instance
