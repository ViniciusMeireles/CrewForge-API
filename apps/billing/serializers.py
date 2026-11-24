from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.billing import entitlements
from apps.billing.choices import (
    BillingCycleChoices,
    CurrencyChoices,
    SubscriptionStatusChoices,
)
from apps.billing.models.plan import Plan


class EntitlementsSerializer(serializers.Serializer):
    max_members = serializers.IntegerField(allow_null=True, read_only=True)
    max_teams = serializers.IntegerField(allow_null=True, read_only=True)
    storage_bytes = serializers.IntegerField(allow_null=True, read_only=True)
    audit = serializers.BooleanField(read_only=True)
    audit_retention_days = serializers.IntegerField(allow_null=True, read_only=True)


class PlanSerializer(serializers.ModelSerializer):
    currency = serializers.ChoiceField(choices=CurrencyChoices.choices, read_only=True)
    entitlements = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = [
            'id',
            'code',
            'name',
            'description',
            'monthly_price',
            'annual_price',
            'currency',
            'trial_days',
            'is_free',
            'is_default',
            'entitlements',
        ]
        read_only_fields = fields

    @extend_schema_field(EntitlementsSerializer)
    def get_entitlements(self, obj: Plan) -> dict:
        return {
            'max_members': entitlements.value(obj, entitlements.MAX_MEMBERS),
            'max_teams': entitlements.value(obj, entitlements.MAX_TEAMS),
            'storage_bytes': entitlements.storage_bytes(obj),
            'audit': entitlements.value(obj, entitlements.AUDIT),
            'audit_retention_days': entitlements.value(
                obj, entitlements.AUDIT_RETENTION_DAYS
            ),
        }


class UsageSerializer(serializers.Serializer):
    current = serializers.IntegerField(read_only=True)
    max = serializers.IntegerField(allow_null=True, read_only=True)


class SubscriptionUsageSerializer(serializers.Serializer):
    members = UsageSerializer(read_only=True)
    teams = UsageSerializer(read_only=True)
    storage = UsageSerializer(read_only=True)


class SubscriptionDetailSerializer(serializers.Serializer):
    plan = PlanSerializer(read_only=True)
    status = serializers.ChoiceField(
        choices=SubscriptionStatusChoices.choices, read_only=True
    )
    cycle = serializers.ChoiceField(
        choices=BillingCycleChoices.choices, allow_null=True, read_only=True
    )
    trial_ends_at = serializers.DateTimeField(allow_null=True, read_only=True)
    is_complimentary = serializers.BooleanField(read_only=True)
    usage = SubscriptionUsageSerializer(read_only=True)
