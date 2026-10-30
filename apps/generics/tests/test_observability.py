import json
import logging
import sys
import uuid
from unittest import mock

from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.tests.mixins import APITestCaseMixin
from apps.generics.logging import JsonFormatter, RequestIdFilter, request_id_var
from config.settings.observability import init_sentry


class RequestIdTestCase(APITestCase):
    def _session_url(self):
        return reverse('accounts:session-config')

    def test_valid_incoming_id_is_echoed(self):
        response = self.client.get(self._session_url(), HTTP_X_REQUEST_ID='abc-123')
        self.assertEqual(response['X-Request-ID'], 'abc-123')

    def test_missing_id_gets_a_uuid(self):
        response = self.client.get(self._session_url())
        self.assertEqual(
            str(uuid.UUID(response['X-Request-ID'])), response['X-Request-ID']
        )

    def test_invalid_incoming_id_is_replaced(self):
        response = self.client.get(
            self._session_url(), HTTP_X_REQUEST_ID='bad id\nwith newline'
        )
        self.assertNotEqual(response['X-Request-ID'], 'bad id\nwith newline')
        uuid.UUID(response['X-Request-ID'])

    def test_trailing_newline_id_is_replaced(self):
        response = self.client.get(self._session_url(), HTTP_X_REQUEST_ID='abc\n')
        uuid.UUID(response['X-Request-ID'])

    def test_probes_carry_the_id(self):
        response = self.client.get('/healthz', HTTP_X_REQUEST_ID='probe-1')
        self.assertEqual(response['X-Request-ID'], 'probe-1')

    def test_django_request_logs_carry_the_id(self):
        with self.assertLogs('django.request', level='WARNING') as logs:
            self.client.get('/api/does-not-exist/', HTTP_X_REQUEST_ID='late-1')
        record = logs.records[-1]
        RequestIdFilter().filter(record)
        self.assertEqual(record.request_id, 'late-1')
        self.assertNotIn('request', json.loads(JsonFormatter().format(record)))

    @override_settings(CORS_ALLOWED_ORIGINS=['https://spa.example.com'])
    def test_id_is_readable_and_sendable_cross_origin(self):
        response = self.client.get(
            self._session_url(), HTTP_ORIGIN='https://spa.example.com'
        )
        self.assertIn('x-request-id', response['Access-Control-Expose-Headers'].lower())
        preflight = self.client.options(
            self._session_url(),
            HTTP_ORIGIN='https://spa.example.com',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='GET',
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS='x-request-id',
        )
        self.assertIn('x-request-id', preflight['Access-Control-Allow-Headers'].lower())

    def test_id_is_cleared_after_the_request(self):
        self.client.get(self._session_url(), HTTP_X_REQUEST_ID='abc-123')
        self.assertEqual(request_id_var.get(), '')


class JsonLoggingTestCase(SimpleTestCase):
    def _format(self, record):
        RequestIdFilter().filter(record)
        return json.loads(JsonFormatter().format(record))

    def test_record_is_one_json_object(self):
        token = request_id_var.set('req-1')
        try:
            record = logging.LogRecord(
                'security', logging.INFO, __file__, 1, 'event=%s', ('x',), None
            )
            record.security_event = {'event': 'x'}
            data = self._format(record)
        finally:
            request_id_var.reset(token)
        self.assertEqual(data['level'], 'INFO')
        self.assertEqual(data['logger'], 'security')
        self.assertEqual(data['message'], 'event=x')
        self.assertEqual(data['request_id'], 'req-1')
        self.assertEqual(data['security_event'], {'event': 'x'})
        self.assertIn('timestamp', data)

    def test_extra_fields_do_not_override_core_keys(self):
        record = logging.LogRecord('x', logging.ERROR, __file__, 1, 'real', (), None)
        record.level = 'DEBUG'
        record.message_extra = 'kept'
        data = self._format(record)
        self.assertEqual(data['level'], 'ERROR')
        self.assertEqual(data['message_extra'], 'kept')

    def test_stack_info_is_serialized(self):
        record = logging.LogRecord('x', logging.WARNING, __file__, 1, 'm', (), None)
        record.stack_info = 'Stack (most recent call last):\n  here'
        self.assertIn('here', self._format(record)['stack'])

    def test_exception_is_serialized(self):
        try:
            raise ValueError('boom')
        except ValueError:
            record = logging.LogRecord(
                'x', logging.ERROR, __file__, 1, 'failed', (), sys.exc_info()
            )
        data = self._format(record)
        self.assertIn('ValueError: boom', data['exception'])


class SentryTestCase(SimpleTestCase):
    def test_disabled_without_dsn(self):
        with mock.patch('sentry_sdk.init') as init:
            self.assertFalse(init_sentry({}))
        init.assert_not_called()

    def test_enabled_with_dsn_and_no_pii(self):
        with mock.patch('sentry_sdk.init') as init:
            self.assertTrue(
                init_sentry(
                    {
                        'SENTRY_DSN': 'https://k@sentry.example.com/1',
                        'SENTRY_ENVIRONMENT': 'production',
                        'SENTRY_RELEASE': 'abc',
                    }
                )
            )
        kwargs = init.call_args.kwargs
        self.assertEqual(kwargs['dsn'], 'https://k@sentry.example.com/1')
        self.assertFalse(kwargs['send_default_pii'])
        self.assertEqual(kwargs['environment'], 'production')
        self.assertEqual(kwargs['release'], 'abc')


class ClientErrorCodesTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()

    def _assert(self, response, status, code):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.data['error']['code'], code)

    def test_client_errors_have_codes_and_no_traceback(self):
        url = reverse('accounts:invitations-list')
        with self.assertNoLogs('apps.generics.exceptions', level='ERROR'):
            self._assert(
                self.client.generic(
                    'POST', url, '{bad json', content_type='application/json'
                ),
                http_status.HTTP_400_BAD_REQUEST,
                'PARSE_ERROR',
            )
            self._assert(
                self.client.post(url, data='x', content_type='application/xml'),
                http_status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                'UNSUPPORTED_MEDIA_TYPE',
            )
            self._assert(
                self.client.patch(url, data={}, format='json'),
                http_status.HTTP_405_METHOD_NOT_ALLOWED,
                'METHOD_NOT_ALLOWED',
            )
            self._assert(
                self.client.get(reverse('accounts:invitations-detail', args=[999999])),
                http_status.HTTP_404_NOT_FOUND,
                'NOT_FOUND',
            )
