from django.core.exceptions import ImproperlyConfigured
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema_serializer
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.generics.serializers.options import (
    OptionsFilterSetSerializer,
    OptionsModelSerializer,
    OptionsSerializer,
)
from apps.generics.utils.models import get_verbose_name, get_verbose_name_plural
from apps.generics.utils.schema import (
    get_form_options_parameters,
    options_schema_create,
    options_schema_list,
    options_schema_update,
)

OPTIONS_CRUD_ACTIONS = {
    'create': 'form_options_create',
    'update': 'form_options_update',
    'list': 'filter_options',
}

OPTIONS_SCHEMAS = {
    'create': options_schema_create,
    'update': options_schema_update,
    'list': options_schema_list,
}

OPTIONS_SERIALIZER_DESCRIPTIONS = {
    'create': (_('Form options to create a {name}.'), get_verbose_name),
    'update': (_('Form options to update a {name}.'), get_verbose_name),
    'list': (_('Filter options for listing {name}.'), get_verbose_name_plural),
}


class OptionsBaseModelMixin:
    """
    Runtime behavior of the options endpoints.

    ``GET form-options-create/`` and ``GET form-options-update/`` describe the
    selectable fields (choices and writable relations) of the serializer the
    ViewSet uses for ``create`` and ``update``. ``GET filter-options/`` describes
    the selectable filters (choices, relations and ``order_by``) of the
    ``filterset_class`` used by ``list``. A ViewSet declares the routes it exposes
    with ``FormOptionsMixin`` and ``FilterOptionsMixin``.

    ViewSet attributes:

    - ``options_custom_actions``: maps a custom ``@action`` to the options action
      the ViewSet declares for it. A ``GET`` source describes the action
      ``filterset_class``; any other describes the serializer the action uses.
    - ``options_serializer_class``: base class of the generated form options
      serializer; defines how relation querysets are scoped.
    - ``options_filterset_serializer_class``: same for the filter options.
    - ``options_search``: ``False`` turns off the ``?<field>=<value>`` search on
      every field of the routes (field selection keeps working).
    - ``options_form_parameters``: extra ``OpenApiParameter`` documented on the
      form-options routes (context params read by option filters).
    """

    options_custom_actions: dict[str, str] = {}
    options_serializer_class = OptionsModelSerializer
    options_filterset_serializer_class = OptionsFilterSetSerializer
    options_search = True
    options_form_parameters = ()
    # Prefix of the generated options serializer names (schema components).
    # Set it when two ViewSets of one model expose options, so their components
    # do not collide (e.g. ``'Platform'``).
    options_component_prefix = ''

    @classmethod
    def get_options_actions_map(cls) -> dict[str, str]:
        """Map each source action to its options action."""
        return OPTIONS_CRUD_ACTIONS | cls.options_custom_actions

    @classmethod
    def get_custom_action(cls, source_action: str):
        """The ``@action`` function named in ``options_custom_actions``."""
        func = getattr(cls, source_action, None)
        if getattr(func, 'mapping', None) is None:
            raise ImproperlyConfigured(
                f'{cls.__name__}.options_custom_actions: {source_action!r} is not an '
                '@action of the ViewSet.'
            )
        return func

    @classmethod
    def get_custom_options_kind(cls, source_action: str) -> str:
        """``'list'`` (filter options) for a ``GET`` action, else ``'update'``."""
        mapping = cls.get_custom_action(source_action).mapping
        return 'list' if 'get' in mapping else 'update'

    @classmethod
    def get_options_actions_inverse_map(cls) -> dict[str, str]:
        return {v: k for k, v in cls.get_options_actions_map().items()}

    @classmethod
    def _get_options_cache(cls) -> dict:
        """Options serializer classes built for this ViewSet (not inherited)."""
        if '_options_serializer_class_cache' not in cls.__dict__:
            cls._options_serializer_class_cache = {}
        return cls._options_serializer_class_cache

    @classmethod
    def _get_options_serializer_class(cls, serializer_class, view_action, kind=None):
        """
        Build (once per ViewSet) the options serializer for a source serializer.

        The generated ``Meta`` inherits the source ``Meta`` (model, fields,
        read_only_fields, extra_kwargs) and keeps a reference to the source in
        ``Meta.serializer_class``, which ``OptionsModelSerializer`` uses to
        respect the source declared fields.
        """
        if issubclass(serializer_class, OptionsSerializer):
            return serializer_class
        cache = cls._get_options_cache()
        key = (serializer_class, cls.options_serializer_class, view_action)
        if key not in cache:
            meta_bases = ()
            if serializer_meta := getattr(serializer_class, 'Meta', None):
                meta_bases = (serializer_meta,)
            model = serializer_class.Meta.model
            options_class = type(
                f'Options{view_action}{cls.options_component_prefix}{model.__name__}',
                (cls.options_serializer_class,),
                {
                    'Meta': type(
                        'Meta', meta_bases, {'serializer_class': serializer_class}
                    ),
                },
            )
            cache[key] = cls._describe_options_serializer_class(
                options_class, model, kind or view_action
            )
        return cache[key]

    @classmethod
    def _get_filter_options_serializer_class(cls, filterset_class, view_action='List'):
        """Build (once per ViewSet) the options serializer for a filterset."""
        cache = cls._get_options_cache()
        key = (filterset_class, cls.options_filterset_serializer_class, view_action)
        if key not in cache:
            model = filterset_class._meta.model
            options_class = type(
                f'Options{view_action}{cls.options_component_prefix}{model.__name__}',
                (cls.options_filterset_serializer_class,),
                {
                    'Meta': type(
                        'Meta',
                        (),
                        {'model': model, 'filterset_class': filterset_class},
                    )
                },
            )
            cache[key] = cls._describe_options_serializer_class(
                options_class, model, 'list'
            )
        return cache[key]

    @staticmethod
    def _describe_options_serializer_class(options_class, model, view_action):
        description = OPTIONS_SERIALIZER_DESCRIPTIONS.get(view_action.lower())
        if description is None:
            return options_class
        message, get_name = description
        return extend_schema_serializer(
            description=format_lazy(message, name=get_name(model))
        )(options_class)

    def get_options_filterset_class(self, filterset_class=None):
        """
        Filterset whose filters are described by ``filter-options/``: the
        ``filterset_class`` of a ViewSet that filters with ``DjangoFilterBackend``
        (or the given one, e.g. from a custom action).
        """
        filter_backends = getattr(self, 'filter_backends', None) or ()
        if not any(
            isinstance(backend, type) and issubclass(backend, DjangoFilterBackend)
            for backend in filter_backends
        ):
            return None
        if filterset_class is None:
            filterset_class = getattr(self, 'filterset_class', None)
        if filterset_class is None or getattr(filterset_class, '_meta', None) is None:
            return None
        if filterset_class._meta.model is None:
            return None
        return filterset_class

    def get_options_serializer_class(self):
        """
        Resolve the options serializer for the current options action.

        ``self.action`` is temporarily switched to the mapped CRUD action so the
        ViewSet's own ``get_serializer_class`` override picks the same serializer
        the write endpoint uses (e.g. ``TeamMemberUpdateSerializer`` for update).
        """
        options_action = self.action
        source_action = self.get_options_actions_inverse_map()[options_action]
        if source_action not in OPTIONS_CRUD_ACTIONS:
            return self.get_custom_options_serializer_class(source_action)
        if source_action == 'list':
            if (filterset_class := self.get_options_filterset_class()) is None:
                return None
            return self._get_filter_options_serializer_class(filterset_class)
        self.action = source_action
        try:
            serializer_class = self.get_serializer_class()
        finally:
            self.action = options_action
        return self._get_options_serializer_class(
            serializer_class=serializer_class,
            view_action=source_action.title(),
        )

    def get_custom_options_serializer_class(self, source_action):
        """Options serializer of a custom action named in ``options_actions``."""
        func = self.get_custom_action(source_action)
        kind = self.get_custom_options_kind(source_action)
        view_action = ''.join(part.title() for part in source_action.split('_'))
        if kind == 'list':
            filterset_class = self.get_options_filterset_class(
                func.kwargs.get('filterset_class')
            )
            if filterset_class is None:
                return None
            return self._get_filter_options_serializer_class(
                filterset_class, view_action=view_action
            )
        serializer_class = func.kwargs.get('serializer_class')
        if serializer_class is None:
            options_action = self.action
            self.action = source_action
            try:
                serializer_class = self.get_serializer_class()
            finally:
                self.action = options_action
        return self._get_options_serializer_class(
            serializer_class=serializer_class, view_action=view_action, kind=kind
        )

    def form_options(self, request, *args, **kwargs):
        """Render the options; fields ignore the (empty) instance."""
        if (serializer_class := self.get_options_serializer_class()) is None:
            raise NotFound()
        context = self.get_serializer_context()
        context['options_search'] = self.options_search
        serializer = serializer_class({}, context=context)
        return Response(serializer.to_representation({}))

    def get_options_schema(self) -> dict:
        """``extend_schema`` values of the current options action, if any."""
        source_action = self.get_options_actions_inverse_map().get(self.action)
        if source_action is None:
            return {}
        kind = source_action
        if source_action not in OPTIONS_CRUD_ACTIONS:
            kind = self.get_custom_options_kind(source_action)
        if (serializer_class := self.get_options_serializer_class()) is None:
            return {}
        parameters = get_form_options_parameters(
            serializer_class, search=self.options_search
        )
        if kind != 'list':
            parameters += self.options_form_parameters
        return {
            **OPTIONS_SCHEMAS[kind](serializer_class.Meta.model),
            'responses': serializer_class,
            'parameters': parameters,
        }


class FormOptionsMixin(OptionsBaseModelMixin):
    """Declare ``form-options-create/`` and ``form-options-update/``."""

    @action(detail=False, methods=['get'], url_path='form-options-create')
    def form_options_create(self, request, *args, **kwargs):
        return self.form_options(request, *args, **kwargs)

    @action(detail=False, methods=['get'], url_path='form-options-update')
    def form_options_update(self, request, *args, **kwargs):
        return self.form_options(request, *args, **kwargs)


class FilterOptionsMixin(OptionsBaseModelMixin):
    """Declare ``filter-options/``."""

    @action(detail=False, methods=['get'], url_path='filter-options')
    def filter_options(self, request, *args, **kwargs):
        return self.form_options(request, *args, **kwargs)
