from apps.generics.managers.querysets import BaseManager, BaseQuerySet


class OrganizationProfileQueryset(BaseQuerySet):
    def filter_actives(self):
        return super().filter_actives().filter(organization__is_active=True)

    def filter_inactives(self):
        return self.exclude(is_active=True).exclude(organization__is_active=True)


OrganizationManager = BaseManager.from_queryset(BaseQuerySet)
OrganizationProfileManager = BaseManager.from_queryset(OrganizationProfileQueryset)
