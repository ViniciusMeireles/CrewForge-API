from django.conf import settings
from django.test import SimpleTestCase, override_settings
from django.urls import path, reverse
from rest_framework import status
from rest_framework.settings import api_settings
from rest_framework.test import APITestCase
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.generics.choices import ErrorCode
from apps.generics.exceptions import (
    _get_error_code,
    _get_error_details,
    _get_error_message,
)


class _InternalErrorView(APIView):
    def get(self, request):
        raise RuntimeError('Intentional test error')


urlpatterns = [
    path('trigger-error/', _InternalErrorView.as_view(), name='trigger-error'),
]


class ExceptionHandlerUnitTestCase(SimpleTestCase):
    def test_get_error_code_authentication_failed(self):
        from rest_framework.exceptions import AuthenticationFailed

        code = _get_error_code(AuthenticationFailed())
        self.assertEqual(code, ErrorCode.AUTHENTICATION_ERROR)

    def test_get_error_code_not_authenticated(self):
        from rest_framework.exceptions import NotAuthenticated

        code = _get_error_code(NotAuthenticated())
        self.assertEqual(code, ErrorCode.AUTHENTICATION_ERROR)

    def test_get_error_code_permission_denied(self):
        from rest_framework.exceptions import PermissionDenied

        code = _get_error_code(PermissionDenied())
        self.assertEqual(code, ErrorCode.PERMISSION_DENIED)

    def test_get_error_code_http404(self):
        from django.http import Http404

        code = _get_error_code(Http404())
        self.assertEqual(code, ErrorCode.NOT_FOUND)

    def test_get_error_code_method_not_allowed(self):
        from rest_framework.exceptions import MethodNotAllowed

        code = _get_error_code(MethodNotAllowed('GET'))
        self.assertEqual(code, ErrorCode.METHOD_NOT_ALLOWED)

    def test_get_error_code_not_acceptable(self):
        from rest_framework.exceptions import NotAcceptable

        code = _get_error_code(NotAcceptable())
        self.assertEqual(code, ErrorCode.NOT_ACCEPTABLE)

    def test_get_error_code_throttled(self):
        from rest_framework.exceptions import Throttled

        code = _get_error_code(Throttled())
        self.assertEqual(code, ErrorCode.THROTTLED)

    def test_get_error_code_validation_error(self):
        from rest_framework.exceptions import ValidationError

        code = _get_error_code(ValidationError({'field': ['error']}))
        self.assertEqual(code, ErrorCode.VALIDATION_ERROR)

    def test_get_error_code_unknown_exception(self):
        code = _get_error_code(ValueError('something'))
        self.assertEqual(code, ErrorCode.INTERNAL_ERROR)

    def test_get_error_message_validation(self):
        from rest_framework.exceptions import ValidationError

        exc = ValidationError({'field': ['error']})
        msg = _get_error_message(exc, ErrorCode.VALIDATION_ERROR)
        self.assertEqual(msg, 'One or more fields are invalid.')

    def test_get_error_message_from_string_detail(self):
        from rest_framework.exceptions import PermissionDenied

        exc = PermissionDenied('Custom error message')
        msg = _get_error_message(exc, ErrorCode.PERMISSION_DENIED)
        self.assertEqual(msg, 'Custom error message')

    def test_get_error_message_from_dict_detail(self):
        from rest_framework.exceptions import PermissionDenied

        exc = PermissionDenied({'field1': ['First error'], 'field2': ['Second']})
        msg = _get_error_message(exc, ErrorCode.PERMISSION_DENIED)
        self.assertEqual(msg, 'First error')

    def test_get_error_message_from_list_detail(self):
        from rest_framework.exceptions import PermissionDenied

        exc = PermissionDenied(['First error', 'Second error'])
        msg = _get_error_message(exc, ErrorCode.PERMISSION_DENIED)
        self.assertEqual(msg, 'First error')

    def test_get_error_message_fallback(self):
        msg = _get_error_message(
            ValueError('Something broke'), ErrorCode.INTERNAL_ERROR
        )
        self.assertEqual(msg, 'Something broke')

    def test_get_error_details_validation_dict(self):
        from rest_framework.exceptions import ValidationError

        exc = ValidationError({'email': ['This field is required.']})
        details = _get_error_details(exc)
        self.assertEqual(details, {'email': ['This field is required.']})

    def test_get_error_details_validation_list(self):
        from rest_framework.exceptions import ValidationError

        exc = ValidationError(['Global error'])
        details = _get_error_details(exc)
        self.assertEqual(details, {'non_field_errors': ['Global error']})

    def test_get_error_details_non_validation(self):
        from rest_framework.exceptions import PermissionDenied

        exc = PermissionDenied()
        details = _get_error_details(exc)
        self.assertIsNone(details)


class ExceptionHandlerIntegrationTestCase(APITestCaseMixin, APITestCase):
    def test_validation_error_format(self):
        response = self.client.post(
            reverse('accounts:token_obtain_pair'),
            data={'password': 'passWord*123'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], ErrorCode.VALIDATION_ERROR)
        self.assertIsInstance(response.data['error']['details'], dict)
        self.assertIsNotNone(response.data['error']['message'])

    def test_authentication_error_format(self):
        response = self.client.get(reverse('accounts:members-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], ErrorCode.AUTHENTICATION_ERROR)
        self.assertIsNone(response.data['error']['details'])

    def test_permission_denied_format(self):
        org = self.new_account()
        member = MemberFactory.create(
            organization=org,
            role=MemberRoleChoices.MEMBER,
            user=UserFactory(),
        )
        self.client.force_authenticate(member=member)
        response = self.client.get(reverse('accounts:invitations-list'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], ErrorCode.PERMISSION_DENIED)
        self.assertIsNone(response.data['error']['details'])

    def test_not_found_format(self):
        self.new_account()
        response = self.client.get(
            reverse('accounts:organizations-detail', args=[99999]),
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], ErrorCode.NOT_FOUND)
        self.assertIsNone(response.data['error']['details'])

    def test_method_not_allowed_format(self):
        org = self.new_account()
        response = self.client.post(
            reverse('accounts:organizations-detail', args=[org.id]),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], ErrorCode.METHOD_NOT_ALLOWED)
        self.assertIsNone(response.data['error']['details'])

    def test_not_acceptable_format(self):
        self.new_account()
        response = self.client.get(
            reverse('accounts:organizations-list'),
            HTTP_ACCEPT='application/xml',
        )
        self.assertEqual(response.status_code, status.HTTP_406_NOT_ACCEPTABLE)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], ErrorCode.NOT_ACCEPTABLE)
        self.assertIsNone(response.data['error']['details'])

    @override_settings(
        REST_FRAMEWORK={
            **settings.REST_FRAMEWORK,
            'DEFAULT_THROTTLE_RATES': {'anon': '1/minute', 'user': '1000/hour'},
        }
    )
    def test_throttled_format(self):
        api_settings.__dict__.pop('DEFAULT_THROTTLE_RATES', None)
        api_settings.__dict__.pop('_user_settings', None)
        original_rates = SimpleRateThrottle.THROTTLE_RATES
        SimpleRateThrottle.THROTTLE_RATES = api_settings.DEFAULT_THROTTLE_RATES
        try:
            url = reverse('accounts:organizations-list')
            self.client.get(url)
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
            self.assertIn('error', response.data)
            self.assertEqual(response.data['error']['code'], ErrorCode.THROTTLED)
            self.assertIsNone(response.data['error']['details'])
        finally:
            SimpleRateThrottle.THROTTLE_RATES = original_rates

    @override_settings(ROOT_URLCONF='apps.generics.tests.test_exceptions')
    def test_internal_error_format(self):
        response = self.client.get('/trigger-error/')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], ErrorCode.INTERNAL_ERROR)
        self.assertIsNone(response.data['error']['details'])

    def test_details_null_for_non_validation(self):
        response = self.client.get(reverse('accounts:members-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIsNone(response.data['error']['details'])
