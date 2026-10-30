from datetime import timedelta
from smtplib import SMTPConnectError, SMTPServerDisconnected
from unittest import mock

from celery.schedules import crontab
from django.conf import settings
from django.test import TestCase, override_settings

from apps.accounts import tasks as account_tasks
from apps.generics.tasks import send_email


class BeatScheduleTestCase(TestCase):
    def test_housekeeping_is_scheduled(self):
        schedule = settings.CELERY_BEAT_SCHEDULE
        by_task = {entry['task']: entry['schedule'] for entry in schedule.values()}
        self.assertEqual(
            by_task['apps.accounts.tasks.flush_expired_tokens'],
            crontab(minute=0, hour=3),
        )
        self.assertEqual(
            by_task['apps.accounts.tasks.clear_sessions'], crontab(minute=15, hour=3)
        )
        self.assertEqual(
            by_task['apps.accounts.tasks.expire_invitations'], timedelta(hours=1)
        )

    def test_tasks_run_their_commands(self):
        cases = {
            account_tasks.flush_expired_tokens: 'flushexpiredtokens',
            account_tasks.clear_sessions: 'clearsessions',
            account_tasks.expire_invitations: 'expire_invites',
        }
        for task, command in cases.items():
            with self.subTest(command=command):
                with mock.patch('apps.accounts.tasks.call_command') as call:
                    task.apply()
                call.assert_called_once_with(command)


@override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
class SendEmailTaskTestCase(TestCase):
    email_path = 'apps.accounts.emails.PasswordResetRequestEmail'

    def _run(self, path):
        return send_email.apply(
            kwargs={
                'email_class_path': path,
                'recipient_list': ['a@example.com'],
                'kwargs': {'reset_url': 'https://example.com/reset'},
            }
        )

    def test_retries_transient_failures(self):
        with mock.patch(
            'apps.generics.mails.bases.EmailBase.send',
            side_effect=[SMTPConnectError(421, 'down'), ConnectionRefusedError(), 1],
        ) as send:
            result = self._run(self.email_path)
        self.assertTrue(result.successful())
        self.assertEqual(send.call_count, 3)

    def test_does_not_resend_after_a_mid_session_failure(self):
        with mock.patch(
            'apps.generics.mails.bases.EmailBase.send',
            side_effect=SMTPServerDisconnected('lost'),
        ) as send:
            result = self._run(self.email_path)
        self.assertFalse(result.successful())
        self.assertEqual(send.call_count, 1)

    def test_refuses_classes_outside_the_allowlist(self):
        with (
            mock.patch('apps.generics.mails.bases.EmailBase.send') as send,
            self.assertLogs('apps.generics.tasks', level='ERROR'),
        ):
            self._run('django.core.mail.EmailMessage')
        send.assert_not_called()
