from django.test import SimpleTestCase
from drf_spectacular.generators import SchemaGenerator


class ResponseComponentsTestCase(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.components = SchemaGenerator().get_schema(request=None, public=True)[
            'components'
        ]['schemas']

    def test_response_components_require_every_property(self):
        invitation = self.components['Invitation']
        self.assertEqual(set(invitation['required']), set(invitation['properties']))

    def test_request_components_keep_their_optional_fields(self):
        request = self.components['InvitationRequest']
        self.assertIn('role', request['properties'])
        self.assertNotIn('role', request.get('required', []))
        self.assertNotIn('id', request['properties'])

    def test_options_components_keep_fields_optional(self):
        options = self.components['OptionsCreateInvitation']
        self.assertNotIn('required', options)

    def test_plain_serializers_keep_fields_they_may_omit(self):
        session_config = self.components['SessionConfig']
        self.assertEqual(session_config['required'], ['session_configured'])

    def test_patched_request_components_require_nothing(self):
        patched = self.components['PatchedMemberUpdateRequest']
        self.assertNotIn('required', patched)
