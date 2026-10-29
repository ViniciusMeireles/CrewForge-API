from django.db.models import Prefetch

from apps.accounts.choices import MemberRoleChoices
from apps.generics.managers.querysets import BaseManager, BaseQuerySet


class OrganizationQuerySet(BaseQuerySet):
    def with_owner(self):
        from apps.accounts.models.member import Member

        return self.prefetch_related(
            Prefetch(
                'members',
                queryset=Member.objects.filter(
                    role=MemberRoleChoices.OWNER, is_active=True
                ).select_related('user'),
                to_attr='active_owners',
            )
        )


class OrganizationProfileQueryset(BaseQuerySet):
    def filter_actives(self):
        return super().filter_actives().filter(organization__is_active=True)

    def filter_inactives(self):
        return self.exclude(is_active=True).exclude(organization__is_active=True)


OrganizationManager = BaseManager.from_queryset(OrganizationQuerySet)
OrganizationProfileManager = BaseManager.from_queryset(OrganizationProfileQueryset)
