import logging

from django.db.models import Q
from django.http import FileResponse, Http404
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import backends
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status as http_status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser

from apps.accounts.choices import StoredFileAccess
from apps.accounts.filters.files import StoredFileFilter
from apps.accounts.mixins.views import ModelViewSetMixin
from apps.accounts.models.files import StoredFile
from apps.accounts.permissions.files import StoredFilePermission
from apps.accounts.serializers.files import (
    StoredFileCreateUpdateModelSerializer,
    StoredFileDetailModelSerializer,
    StoredFileListModelSerializer,
)
from apps.generics.utils.schema import (
    extend_schema_create,
    extend_schema_model_view_set,
    extend_schema_partial_update,
    extend_schema_update,
)
from apps.generics.utils.strings import str_to_bool

logger = logging.getLogger(__name__)


@extend_schema_model_view_set(
    model=StoredFile,
    file=extend_schema(
        tags=StoredFile.schema_tags(),
        description=_('Download a file.'),
        responses={
            http_status.HTTP_200_OK: OpenApiResponse(
                response=OpenApiTypes.BYTE,
                description=_('The file content.'),
            ),
            http_status.HTTP_404_NOT_FOUND: OpenApiResponse(
                description=_('File not found.'),
            ),
        },
        parameters=[
            OpenApiParameter(
                name='download',
                type=OpenApiTypes.BOOL,
                description=_('Whether to download the file as an attachment or not.'),
            ),
        ],
    ),
    create=extend_schema_create(
        model=StoredFile,
        responses={http_status.HTTP_201_CREATED: StoredFileDetailModelSerializer},
    ),
    update=extend_schema_update(
        model=StoredFile,
        responses={http_status.HTTP_200_OK: StoredFileDetailModelSerializer},
    ),
    partial_update=extend_schema_partial_update(
        model=StoredFile,
        responses={http_status.HTTP_200_OK: StoredFileDetailModelSerializer},
    ),
)
class StoredFileViewSet(ModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = StoredFileListModelSerializer
    permission_classes = [StoredFilePermission]
    filterset_class = StoredFileFilter
    filter_backends = [backends.DjangoFilterBackend]
    parser_classes = [MultiPartParser, FormParser]
    lookup_field = 'uuid'
    label_expression = StoredFile.label_expression()
    queryset = StoredFile.objects.all()

    def get_queryset(self):
        queryset = super().get_queryset()

        conditions = Q(viewing_permission=StoredFileAccess.PUBLIC)
        if auth_user := self.auth_user:
            if auth_user.is_superuser:
                return queryset
            conditions |= Q(
                viewing_permission=StoredFileAccess.OWNER,
                owner_id=auth_user.id,
            )

        auth_member = self.auth_member
        if auth_member and auth_member.is_active and auth_member.organization_id:
            allowed_permissions = []
            if max_org_level := StoredFileAccess.max_org_level(member=auth_member):
                allowed_permissions = StoredFileAccess.permissions_levels_viewing.get(
                    max_org_level, []
                )
            allowed_permissions = set(allowed_permissions) & set(
                StoredFileAccess.organization_accesses
            )
            conditions |= Q(
                viewing_permission__in=allowed_permissions,
                organization_id=auth_member.organization_id,
            )

        queryset = queryset.filter(conditions, is_active=True)
        if conditions.connector == Q.OR:
            queryset = queryset.distinct()
        return queryset

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return StoredFileCreateUpdateModelSerializer
        elif self.action == 'retrieve':
            return StoredFileDetailModelSerializer
        return super().get_serializer_class()

    @action(detail=True, methods=['get'], url_path='file')
    def file(self, request, uuid=None, *args, **kwargs):
        obj = self.get_object()
        try:
            obj.file.open('rb')
        except Exception as err:
            if obj.file and not getattr(obj.file, 'closed', True):
                obj.file.close()
            logger.error(
                msg=_('Error when trying to open file'),
                exc_info=True,
                extra={'uuid': uuid},
            )
            raise Http404(_('File object not found.')) from err

        return FileResponse(
            obj.file,
            as_attachment=str_to_bool(request.GET.get('download', 'false')),
            filename=obj.download_name,
            content_type=obj.content_type or 'application/octet-stream',
        )
