from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.tests.mixins import APITestCaseMixin
from apps.accounts.tests.permission_matrix import (
    ADMIN,
    ANONYMOUS,
    INACTIVE,
    MANAGER,
    MEMBER,
    OTHER_ORGANIZATION,
    OWNER,
    Action,
    PermissionMatrixMixin,
)

LIST = reverse('accounts:organization_profiles-list')


def _detail(case):
    profile = case.organization.get_profile()
    return reverse('accounts:organization_profiles-detail', args=[profile.pk])


def _website(case):
    return {'website': 'https://updated.example'}


class OrganizationProfilePermissionMatrixTestCase(
    PermissionMatrixMixin, APITestCaseMixin, APITestCase
):
    actions = {
        'list': Action('get', lambda case: LIST),
        'retrieve': Action('get', _detail),
        'update': Action('patch', _detail, _website),
        'delete': Action('delete', _detail),
    }
    matrix = {
        ANONYMOUS: {'list': 401, 'retrieve': 401, 'update': 401, 'delete': 401},
        INACTIVE: {'list': 403, 'retrieve': 403, 'update': 403, 'delete': 403},
        OWNER: {'retrieve': 200, 'update': 200, 'delete': 204},
        ADMIN: {'retrieve': 200, 'update': 200, 'delete': 204},
        MANAGER: {'retrieve': 200, 'update': 403, 'delete': 403},
        MEMBER: {'retrieve': 200, 'update': 403, 'delete': 403},
        OTHER_ORGANIZATION: {'retrieve': 404, 'update': 404, 'delete': 404},
    }
