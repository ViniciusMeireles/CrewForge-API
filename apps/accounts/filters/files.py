from django_filters.rest_framework import filterset

from apps.accounts.mixins.filters import FilterSetMixin
from apps.accounts.models.files import StoredFile


class StoredFileFilter(FilterSetMixin, filterset.FilterSet):
    class Meta:
        model = StoredFile
        fields = {
            'name': ['exact', 'icontains'],
            'original_name': ['exact', 'icontains'],
            'content_type': ['exact'],
            'size': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'viewing_permission': ['exact', 'in'],
            'updating_permission': ['exact', 'in'],
            'owner': ['exact'],
            'organization': ['exact'],
        }
