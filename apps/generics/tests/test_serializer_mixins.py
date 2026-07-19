from django.test import SimpleTestCase
from rest_framework import serializers

from apps.accounts.models.member import Member
from apps.generics.mixins.serializers import ModelSerializerFieldsMixin


class _NestedSerializer(serializers.Serializer):
    name = serializers.CharField()


class OrderableFieldsChoicesTestCase(SimpleTestCase):
    def test_includes_pk_declared_and_model_fields(self):
        class TS(ModelSerializerFieldsMixin, serializers.ModelSerializer):
            class Meta:
                model = Member
                fields = '__all__'

        fields = [c[0] for c in TS.orderable_fields_choices]
        self.assertIn('id', fields)
        self.assertIn('nickname', fields)
        self.assertIn('role', fields)
        self.assertIn('created_at', fields)

    def test_excludes_write_only_fields(self):
        class TS(ModelSerializerFieldsMixin, serializers.ModelSerializer):
            secret = serializers.CharField(write_only=True)

            class Meta:
                model = Member
                fields = '__all__'

        fields = [c[0] for c in TS.orderable_fields_choices]
        self.assertNotIn('secret', fields)
        self.assertIn('nickname', fields)

    def test_excludes_serializer_method_field(self):
        class TS(ModelSerializerFieldsMixin, serializers.ModelSerializer):
            computed = serializers.SerializerMethodField()

            class Meta:
                model = Member
                fields = '__all__'

        fields = [c[0] for c in TS.orderable_fields_choices]
        self.assertNotIn('computed', fields)

    def test_excludes_nested_serializers(self):
        class TS(ModelSerializerFieldsMixin, serializers.ModelSerializer):
            nested = _NestedSerializer()

            class Meta:
                model = Member
                fields = '__all__'

        fields = [c[0] for c in TS.orderable_fields_choices]
        self.assertNotIn('nested', fields)

    def test_descending_entries_have_minus_prefix(self):
        class TS(ModelSerializerFieldsMixin, serializers.ModelSerializer):
            class Meta:
                model = Member
                fields = ['nickname', 'role']

        choices = TS.orderable_fields_choices
        self.assertEqual(choices[0][0], 'nickname')
        self.assertEqual(choices[1][0], '-nickname')
        self.assertEqual(choices[2][0], 'role')
        self.assertEqual(choices[3][0], '-role')

    def test_descending_labels_use_template(self):
        class TS(ModelSerializerFieldsMixin, serializers.ModelSerializer):
            class Meta:
                model = Member
                fields = ['nickname']

        choices = TS.orderable_fields_choices
        self.assertEqual(choices[1][1], 'Descending Nickname')

    def test_uses_verbose_name_from_model(self):
        class TS(ModelSerializerFieldsMixin, serializers.ModelSerializer):
            class Meta:
                model = Member
                fields = ['nickname', 'last_login_at']

        choices = dict(TS.orderable_fields_choices)
        self.assertEqual(choices['nickname'], 'Nickname')
        self.assertEqual(choices['last_login_at'], 'Last login at')

    def test_returns_choices_sorted_by_label(self):
        class TS(ModelSerializerFieldsMixin, serializers.ModelSerializer):
            class Meta:
                model = Member
                fields = ['nickname', 'role', 'id']

        labels = [c[1] for c in TS.orderable_fields_choices if not c[0].startswith('-')]
        self.assertEqual(labels, sorted(labels))

    def test_skips_reverse_relations(self):
        class TS(ModelSerializerFieldsMixin, serializers.ModelSerializer):
            class Meta:
                model = Member
                fields = '__all__'

        choices = TS.orderable_fields_choices
        fields = [c[0] for c in choices if not c[0].startswith('-')]
        fields_no_prefix = {f.lstrip('-') for f in fields}

        self.assertNotIn('owned_organizations', fields_no_prefix)
        self.assertNotIn('teams', fields_no_prefix)
