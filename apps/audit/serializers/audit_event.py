from django.core.exceptions import FieldDoesNotExist
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.audit.models.audit_event import AuditEvent
from apps.audit.services import model_for_target_type


class AuditActorSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(allow_null=True)
    member_id = serializers.IntegerField(allow_null=True)
    label = serializers.CharField()


class AuditImpersonatorSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    label = serializers.CharField()


class AuditEventChangeSerializer(serializers.Serializer):
    field = serializers.CharField()
    field_display = serializers.CharField()
    before = serializers.JSONField(allow_null=True)
    after = serializers.JSONField(allow_null=True)


class AuditEventSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source='get_action_display')
    actor = serializers.SerializerMethodField()
    impersonator = serializers.SerializerMethodField()
    changes = serializers.SerializerMethodField()

    class Meta:
        model = AuditEvent
        fields = [
            'id',
            'created_at',
            'action',
            'action_display',
            'actor_type',
            'actor',
            'impersonator',
            'organization_id',
            'target_type',
            'target_id',
            'target_label',
            'changes',
            'metadata',
            'ip',
        ]
        read_only_fields = fields

    @extend_schema_field(AuditActorSerializer(allow_null=True))
    def get_actor(self, obj: AuditEvent) -> dict | None:
        if not (obj.actor_user_id or obj.actor_member_id):
            return None
        return {
            'user_id': obj.actor_user_id,
            'member_id': obj.actor_member_id,
            'label': obj.actor_label,
        }

    @extend_schema_field(AuditImpersonatorSerializer(allow_null=True))
    def get_impersonator(self, obj: AuditEvent) -> dict | None:
        if not obj.impersonator_id:
            return None
        return {'user_id': obj.impersonator_id, 'label': str(obj.impersonator)}

    @extend_schema_field(AuditEventChangeSerializer(many=True))
    def get_changes(self, obj: AuditEvent) -> list[dict]:
        model = model_for_target_type(obj.target_type)
        return [
            {**change, 'field_display': self.field_display(model, change['field'])}
            for change in obj.changes
        ]

    @staticmethod
    def field_display(model, field_name: str) -> str:
        if model is None:
            return field_name
        try:
            return str(model._meta.get_field(field_name).verbose_name)
        except FieldDoesNotExist:
            return field_name
