from django.test import TestCase

from apps.generics.utils.db import queue_on_commit


class QueueOnCommitTestCase(TestCase):
    def test_runs_after_commit(self):
        calls = []
        with self.captureOnCommitCallbacks(execute=True):
            queue_on_commit(lambda: calls.append('sent'), 'a test email')
            self.assertEqual(calls, [])
        self.assertEqual(calls, ['sent'])

    def test_failure_is_logged_not_raised(self):
        def fail():
            raise RuntimeError('broker down')

        with (
            self.assertLogs('apps.generics.utils.db', level='ERROR') as logs,
            self.captureOnCommitCallbacks(execute=True),
        ):
            queue_on_commit(fail, 'a test email')
        self.assertIn('Could not queue a test email', logs.output[0])
