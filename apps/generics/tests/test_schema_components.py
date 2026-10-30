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

    def test_paginated_options_results_are_a_list(self):
        results = self.components['PaginatedIntOptions']['properties']['results']
        self.assertEqual(results['type'], 'array')
        self.assertEqual(results['items']['$ref'], '#/components/schemas/OptionInt')

    def test_paginated_lists_always_have_next_and_previous(self):
        page = self.components['PaginatedInvitationList']
        self.assertEqual(
            set(page['required']), {'count', 'next', 'previous', 'results'}
        )

    def test_audit_metadata_is_an_object(self):
        metadata = self.components['AuditEvent']['properties']['metadata']
        self.assertEqual(metadata['type'], 'object')
        self.assertIn('additionalProperties', metadata)

    def test_tokens_moved_to_cookies_are_optional_in_bodies(self):
        for name, fields in (
            ('TokenObtainPair', {'access', 'refresh'}),
            ('InvitationAcceptSuccess', {'access', 'refresh'}),
            ('Signup', {'access', 'refresh'}),
            ('UserCreateSignup', {'auth_token'}),
            ('UserCreateWithInvite', {'auth_token'}),
            ('TokenRefresh', {'access', 'refresh'}),
        ):
            with self.subTest(component=name):
                self.assertFalse(
                    fields & set(self.components[name].get('required', []))
                )

    def test_non_token_fields_named_like_tokens_stay_required(self):
        self.assertIn('access', self.components['MemberSession']['required'])

    def test_patched_request_components_require_nothing(self):
        patched = self.components['PatchedMemberUpdateRequest']
        self.assertNotIn('required', patched)
