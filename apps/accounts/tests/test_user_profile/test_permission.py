from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.accounts.tests.permission_matrix import (
    ANONYMOUS,
    NO_SESSION,
    Action,
    PermissionMatrixMixin,
)

PROFILE = reverse('accounts:users-me')
CHANGE_PASSWORD = reverse('accounts:users-me-change-password')
ACTIVITY = reverse('accounts:users-me-activity')


class UserProfilePermissionMatrixTestCase(
    PermissionMatrixMixin, APITestCaseMixin, APITestCase
):
    actions = {
        'retrieve': Action('get', lambda case: PROFILE),
        'update': Action(
            'patch', lambda case: PROFILE, lambda case: {'first_name': 'X'}
        ),
        'update_language': Action(
            'patch', lambda case: PROFILE, lambda case: {'preferred_language': 'pt-br'}
        ),
        'change_password': Action(
            'post',
            lambda case: CHANGE_PASSWORD,
            lambda case: {
                'current_password': 'passWord*123',
                'new_password': 'newPass*456',
            },
        ),
        'activity': Action('get', lambda case: ACTIVITY),
    }
    matrix = {
        ANONYMOUS: {
            'retrieve': 401,
            'update': 401,
            'update_language': 401,
            'change_password': 401,
            'activity': 401,
        },
        NO_SESSION: {'retrieve': 200, 'activity': 200},
    }

    def setUp(self):
        self.organization = OrganizationFactory()
