from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.billing import entitlements
from apps.billing.choices import (
    BillingCycleChoices,
    BrazilStateChoices,
    ChangeKindChoices,
    CurrencyChoices,
    SubscriptionStatusChoices,
    TaxIdKindChoices,
)
from apps.billing.models.billing_profile import BillingProfile
from apps.billing.models.invoice import Invoice
from apps.billing.models.plan import Plan
from apps.billing.validators import (
    normalize_digits,
    validate_postal_code,
    validate_tax_id,
)


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


class PlanSummarySerializer(serializers.Serializer):
    code = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)


class NextChargeSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    date = serializers.DateField(read_only=True)


class ScheduledChangeSerializer(serializers.Serializer):
    plan = PlanSummarySerializer(read_only=True)
    cycle = serializers.ChoiceField(choices=BillingCycleChoices.choices, read_only=True)
    effective_at = serializers.DateTimeField(read_only=True)


class PendingChangeSerializer(serializers.Serializer):
    plan = PlanSummarySerializer(read_only=True)
    cycle = serializers.ChoiceField(choices=BillingCycleChoices.choices, read_only=True)
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True, read_only=True
    )
    invoice = serializers.IntegerField(allow_null=True, read_only=True)
    payment_url = serializers.URLField(allow_null=True, read_only=True)


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
    current_period_end = serializers.DateTimeField(allow_null=True, read_only=True)
    next_charge = NextChargeSerializer(allow_null=True, read_only=True)
    cancel_at_period_end = serializers.BooleanField(read_only=True)
    scheduled_change = ScheduledChangeSerializer(allow_null=True, read_only=True)
    pending_change = PendingChangeSerializer(allow_null=True, read_only=True)
    billing_profile_complete = serializers.BooleanField(read_only=True)


class ChangeRequestSerializer(serializers.Serializer):
    plan = serializers.SlugRelatedField(slug_field='code', queryset=Plan.objects.none())
    cycle = serializers.ChoiceField(choices=BillingCycleChoices.choices)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['plan'].queryset = Plan.objects.offered()


class ChangePreviewSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=ChangeKindChoices.choices, read_only=True)
    charged_now = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    recurring_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    recurring_from = serializers.DateField(read_only=True)
    effective_at = serializers.DateTimeField(read_only=True)
    requires_billing_profile = serializers.BooleanField(read_only=True)


@extend_schema_field({'type': 'string', 'nullable': True})
class TaxIdField(serializers.CharField):
    pass


class BillingProfileSerializer(serializers.ModelSerializer):
    tax_id = TaxIdField(max_length=18)
    postal_code = serializers.CharField(max_length=9)
    tax_id_masked = serializers.CharField(source='masked_tax_id', read_only=True)
    tax_id_kind = serializers.ChoiceField(
        choices=TaxIdKindChoices.choices, read_only=True
    )
    state = serializers.ChoiceField(choices=BrazilStateChoices.choices)

    class Meta:
        model = BillingProfile
        fields = [
            'legal_name',
            'tax_id',
            'tax_id_masked',
            'tax_id_kind',
            'email',
            'postal_code',
            'street',
            'number',
            'complement',
            'district',
            'city',
            'state',
            'updated_at',
        ]
        read_only_fields = ['updated_at']
        extra_kwargs = {'complement': {'required': False, 'allow_blank': True}}

    def validate_tax_id(self, value: str) -> str:
        digits = normalize_digits(value)
        try:
            validate_tax_id(digits)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from None
        return digits

    def validate_postal_code(self, value: str) -> str:
        digits = normalize_digits(value)
        try:
            validate_postal_code(digits)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from None
        return digits

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.context.get('can_manage', False):
            data['tax_id'] = None
        return data


class InvoiceSerializer(serializers.ModelSerializer):
    description = serializers.CharField(read_only=True)
    payment_url = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            'id',
            'kind',
            'description',
            'amount',
            'issued_at',
            'due_date',
            'paid_at',
            'status',
            'payment_url',
        ]
        read_only_fields = fields

    def get_payment_url(self, obj: Invoice) -> str | None:
        if not self.context.get('can_manage', False) or not obj.payment_url:
            return None
        return obj.payment_url


class ChangeResultSerializer(serializers.Serializer):
    subscription = SubscriptionDetailSerializer(read_only=True)
    payment_url = serializers.URLField(allow_null=True, read_only=True)
