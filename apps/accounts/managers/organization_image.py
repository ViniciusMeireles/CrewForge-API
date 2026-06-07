from apps.generics.managers.querysets import BaseManager, BaseQuerySet


class OrganizationImageQueryset(BaseQuerySet):
    def filter_actives(self):
        return (
            super()
            .filter_actives()
            .filter(
                profile__is_active=True,
                profile__organization__is_active=True,
                image__is_active=True,
            )
        )

    def filter_inactives(self):
        return (
            self.exclude(is_active=True)
            .exclude(profile__is_active=True)
            .exclude(
                profile__organization__is_active=True,
            )
            .exclude(
                image__is_active=True,
            )
        )


OrganizationImageManager = BaseManager.from_queryset(OrganizationImageQueryset)
