from apps.generics.managers.querysets import BaseManager, BaseQuerySet

StoredFileManager = BaseManager.from_queryset(BaseQuerySet)
