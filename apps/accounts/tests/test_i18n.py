from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import translation
from drf_spectacular.generators import SchemaGenerator
from rest_framework import serializers
from rest_framework.test import APITestCase

from apps.accounts.models.member import Member
from apps.generics.mails.bases import CTAEmail
from apps.generics.mixins.serializers import ModelSerializerFieldsMixin

VALIDATION_ERROR_URL = 'accounts:token_obtain_pair'
MEMBERS_LIST_URL = 'accounts:members-list'


class LocaleMiddlewareNegotiationTestCase(APITestCase):
    def setUp(self):
        self.url = reverse('accounts:session-config')

    def test_portuguese_sets_content_language(self):
        response = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE='pt-BR,pt;q=0.9')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Language'], 'pt-br')
        self.assertIn('Accept-Language', response.headers['Vary'])

    def test_english_sets_content_language(self):
        response = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE='en-US,en;q=0.9')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Language'], 'en')

    def test_bare_portuguese_maps_to_pt_br(self):
        response = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE='pt')
        self.assertEqual(response.headers['Content-Language'], 'pt-br')

    def test_unsupported_language_falls_back_to_default(self):
        response = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE='fr-FR,fr;q=0.9')
        self.assertEqual(response.headers['Content-Language'], 'en')

    def test_default_language_without_header(self):
        response = self.client.get(self.url)
        self.assertEqual(response.headers['Content-Language'], 'en')


class MiddlewareConfigurationTestCase(SimpleTestCase):
    def test_locale_middleware_sits_between_session_and_common(self):
        middleware = settings.MIDDLEWARE
        locale = 'django.middleware.locale.LocaleMiddleware'
        session = 'django.contrib.sessions.middleware.SessionMiddleware'
        common = 'django.middleware.common.CommonMiddleware'
        self.assertIn(locale, middleware)
        self.assertLess(middleware.index(session), middleware.index(locale))
        self.assertLess(middleware.index(locale), middleware.index(common))


class CatalogTranslationTestCase(SimpleTestCase):
    def test_translated_under_portuguese(self):
        with translation.override('pt-br'):
            self.assertEqual(
                translation.gettext('Permission denied'), 'Permissão negada'
            )
            self.assertEqual(translation.gettext('Owner'), 'Proprietário')
            self.assertEqual(translation.gettext('Team'), 'Equipe')

    def test_english_returns_msgid(self):
        with translation.override('en'):
            self.assertEqual(
                translation.gettext('Permission denied'), 'Permission denied'
            )
            self.assertEqual(translation.gettext('Owner'), 'Owner')

    def test_placeholders_survive_translation(self):
        with translation.override('pt-br'):
            rendered = translation.gettext('Not allowed to set the %(role)s role.') % {
                'role': 'admin'
            }
            self.assertEqual(rendered, 'Não é permitido definir a função admin.')

    def test_lazy_cta_default_resolves_per_language(self):
        cta = CTAEmail(url='https://example.com')
        with translation.override('pt-br'):
            self.assertEqual(str(cta.text), 'Clique aqui')
        with translation.override('en'):
            self.assertEqual(str(cta.text), 'Click Here')

    def test_model_verbose_names_resolve_per_language(self):
        with translation.override('pt-br'):
            self.assertEqual(str(Member._meta.verbose_name), 'Membro')
        with translation.override('en'):
            self.assertEqual(str(Member._meta.verbose_name), 'Member')


class OrderByLabelTranslationTestCase(SimpleTestCase):
    def _choices(self) -> dict:
        class TS(ModelSerializerFieldsMixin, serializers.ModelSerializer):
            class Meta:
                model = Member
                fields = '__all__'

        return dict(TS.orderable_fields_choices)

    def test_descending_label_translated(self):
        with translation.override('pt-br'):
            choices = self._choices()
            self.assertEqual(choices['nickname'], 'Apelido')
            self.assertEqual(choices['-nickname'], 'Apelido (decrescente)')

    def test_descending_label_english(self):
        with translation.override('en'):
            choices = self._choices()
            self.assertEqual(choices['-nickname'], 'Descending Nickname')


class SwaggerTranslationTestCase(APITestCase):
    @override_settings(DEBUG=True, API_DOCS_PUBLIC=None)
    def test_swagger_description_translated(self):
        response = self.client.get(reverse('swagger-ui'), HTTP_ACCEPT_LANGUAGE='pt-BR')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Documentação da API', response.content.decode())

    @override_settings(DEBUG=True, API_DOCS_PUBLIC=None)
    def test_swagger_description_english(self):
        response = self.client.get(reverse('swagger-ui'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('API documentation', response.content.decode())


class TranslatedErrorMessagesTestCase(APITestCase):
    def test_validation_error_translated(self):
        response = self.client.post(
            reverse(VALIDATION_ERROR_URL),
            data={},
            format='json',
            HTTP_ACCEPT_LANGUAGE='pt-BR',
        )
        self.assertEqual(response.status_code, 400)
        error = response.data['error']
        self.assertEqual(error['code'], 'VALIDATION_ERROR')
        self.assertEqual(error['message'], 'Um ou mais campos são inválidos.')

    def test_validation_error_details_translated(self):
        response = self.client.post(
            reverse(VALIDATION_ERROR_URL),
            data={},
            format='json',
            HTTP_ACCEPT_LANGUAGE='pt-BR',
        )
        self.assertEqual(response.status_code, 400)
        details = response.data['error']['details']
        self.assertEqual(details['username'][0], 'Este campo é obrigatório.')
        self.assertEqual(details['password'][0], 'Este campo é obrigatório.')

    def test_validation_error_english(self):
        response = self.client.post(
            reverse(VALIDATION_ERROR_URL), data={}, format='json'
        )
        self.assertEqual(response.status_code, 400)
        error = response.data['error']
        self.assertEqual(error['code'], 'VALIDATION_ERROR')
        self.assertEqual(error['message'], 'One or more fields are invalid.')

    def test_authentication_error_translated(self):
        response = self.client.get(
            reverse(MEMBERS_LIST_URL), HTTP_ACCEPT_LANGUAGE='pt-BR'
        )
        self.assertEqual(response.status_code, 401)
        error = response.data['error']
        self.assertEqual(error['code'], 'AUTHENTICATION_ERROR')
        self.assertEqual(
            error['message'], 'As credenciais de autenticação não foram fornecidas.'
        )


class SchemaTranslationTestCase(SimpleTestCase):
    def _schema(self, language):
        with translation.override(language):
            return SchemaGenerator().get_schema(request=None, public=True)

    def _tags(self, schema):
        return {
            str(tag)
            for operations in schema['paths'].values()
            for operation in operations.values()
            if isinstance(operation, dict)
            for tag in operation.get('tags', [])
        }

    def test_tags_translated_per_language(self):
        portuguese = self._tags(self._schema('pt-br'))
        english = self._tags(self._schema('en'))
        self.assertTrue(
            {'Convites', 'Autenticação', 'Cadastro', 'Sessão'} <= portuguese
        )
        self.assertTrue(
            {'Invitations', 'Authentication', 'Signup', 'Session'} <= english
        )
        self.assertFalse(english & {'Convites', 'Autenticação', 'Cadastro'})

    def test_auth_endpoints_share_authentication_tag(self):
        schema = self._schema('en')
        auth_operations = [
            operation
            for path, operations in schema['paths'].items()
            if path.startswith('/api/auth/')
            for operation in operations.values()
            if isinstance(operation, dict)
        ]
        self.assertTrue(auth_operations)
        for operation in auth_operations:
            tags = [str(tag) for tag in operation['tags']]
            self.assertEqual(tags, ['Authentication'])

    def test_auth_descriptions_follow_language(self):
        for language, prefix in (('pt-br', 'Obtém'), ('en', 'Obtain')):
            with self.subTest(language=language):
                operation = self._schema(language)['paths']['/api/auth/token/']['post']
                self.assertTrue(str(operation['description']).startswith(prefix))


class AppVerboseNameTranslationTestCase(SimpleTestCase):
    def test_app_names_translated(self):
        for language, expected in (
            ('pt-br', {'accounts': 'Contas', 'teams': 'Equipes'}),
            ('en', {'accounts': 'Accounts', 'teams': 'Teams'}),
        ):
            with self.subTest(language=language), translation.override(language):
                for label, name in expected.items():
                    self.assertEqual(str(apps.get_app_config(label).verbose_name), name)
