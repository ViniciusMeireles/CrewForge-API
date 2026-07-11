from apps.generics.managers.querysets import BaseManager, BaseQuerySet


class MemberQuerySet(BaseQuerySet):
    def filter_actives(self):
        return (
            super()
            .filter_actives()
            .filter(
                organization__is_active=True,
            )
        )

    def filter_inactives(self):
        return self.exclude(is_active=True).exclude(
            organization__is_active=True,
        )


MemberManager = BaseManager.from_queryset(MemberQuerySet)
