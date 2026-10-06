import re

from django.core.exceptions import ImproperlyConfigured
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend, filterset
from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.generics.serializers.options import (
    OptionsFilterSetSerializer,
    OptionsModelSerializer,
    OptionsSerializer,
)
from apps.generics.utils.filters import orderable_filter_factory
from apps.generics.utils.models import get_verbose_name, get_verbose_name_plural
from apps.generics.utils.schema import (
    extend_schema_options_create,
    extend_schema_options_list,
    extend_schema_options_update,
    get_form_options_parameters,
)


class OrderableModelViewSetMetaclass(type):
    """
    Add an ``order_by`` filter to ``filterset_class`` when the ViewSet sets
    ``auto_orderable_filter = True``. Orderable fields come from the ``list``
    serializer.
    """

    def __new__(cls, name, bases, attrs):
        klass = super().__new__(cls, name, bases, attrs)
        if not getattr(klass, 'auto_orderable_filter', False):
            return klass
        http_method_names = getattr(klass, 'http_method_names', [])
        if http_method_names and 'get' not in http_method_names:
            return klass
        if not cls._get_filterset_class(klass=klass):
            return klass
        klass.filterset_class = cls._orderable_filter_factory(klass=klass)
        return klass

    @classmethod
    def _get_filterset_class(cls, klass) -> type[filterset.FilterSet] | None:
        view_obj = klass()
        filterset_class = getattr(view_obj, 'filterset_class', None)
        if not filterset_class or not issubclass(filterset_class, filterset.FilterSet):
            return None
        return filterset_class

    @classmethod
    def _get_list_serializer_class(cls, klass: type) -> type[serializers.Serializer]:
        view_obj = klass()
        view_obj.action = 'list'
        return view_obj.get_serializer_class()

    @classmethod
    def _orderable_filter_factory(cls, klass: type) -> type[filterset.FilterSet]:
        filterset_class: type[filterset.FilterSet] = cls._get_filterset_class(  # type: ignore
            klass=klass
        )
        serializer_class = cls._get_list_serializer_class(klass=klass)
        return orderable_filter_factory(
            serializer_class=serializer_class,
            filterset_class=filterset_class,
        )


OPTIONS_CRUD_ACTIONS = frozenset({'create', 'update', 'list'})

OPTIONS_SERIALIZER_DESCRIPTIONS = {
    'create': (_('Form options to create a {name}.'), get_verbose_name),
    'update': (_('Form options to update a {name}.'), get_verbose_name),
    'list': (_('Filter options for listing {name}.'), get_verbose_name_plural),
}


class OptionsBaseModelMixin:
    """
    Runtime behavior of the form-options endpoints.

    ``GET form-options-create/`` and ``GET form-options-update/`` describe the
    selectable fields (choices and writable relations) of the serializer the
    ViewSet uses for ``create`` and ``update``. ``GET filter-options/`` describes
    the selectable filters (choices, relations and ``order_by``) of the
    ``filterset_class`` used by ``list``. The routes themselves are registered by
    ``OptionsModelViewSetMetaclass``.

    ViewSet attributes:

    - ``options_actions``: CRUD actions that get an options route; ``()`` disables
      them (use it when a relation points to a model without organization scope).
      It also accepts the name of a custom ``@action``: a ``GET`` action gets
      ``<url_path>/filter-options/`` (from the action ``filterset_class``), any
      other gets ``form-options-<url_path>/`` (from the serializer the action
      uses). The route keeps the action ``permission_classes``.
    - ``options_serializer_class``: base class of the generated form options
      serializer; defines how relation querysets are scoped.
    - ``options_filterset_serializer_class``: same for the filter options.
    - ``options_search``: ``False`` turns off the ``?<field>=<value>`` search on
      every field of the routes (field selection keeps working).
    - ``url_path_options_*`` / ``action_options_*``: route path and action name.

    The routes are built when the ViewSet class is created, so
    ``get_serializer_class()`` runs once **without a request**: guard any access
    with ``getattr(self, 'request', None)``. Build errors raise
    ``ImproperlyConfigured`` at startup.
    """

    url_path_options_create = 'form-options-create'
    url_path_options_update = 'form-options-update'
    url_path_options_list = 'filter-options'
    action_options_create = 'form_options_create'
    action_options_update = 'form_options_update'
    action_options_list = 'filter_options'
    options_actions = ('create', 'update', 'list')
    options_serializer_class = OptionsModelSerializer
    options_filterset_serializer_class = OptionsFilterSetSerializer
    options_search = True

    @classmethod
    def get_options_actions_map(cls) -> dict[str, str]:
        """Map each source action (see ``options_actions``) to its options action."""
        actions_map = {
            'create': cls.action_options_create,
            'update': cls.action_options_update,
            'list': cls.action_options_list,
        }
        for source_action in cls.options_actions:
            if source_action not in OPTIONS_CRUD_ACTIONS:
                kind = cls.get_custom_options_kind(source_action)
                prefix = 'filter_options' if kind == 'list' else 'form_options'
                actions_map[source_action] = f'{prefix}_{source_action}'
        return actions_map

    @classmethod
    def get_custom_action(cls, source_action: str):
        """The ``@action`` function named in ``options_actions``."""
        func = getattr(cls, source_action, None)
        if getattr(func, 'mapping', None) is None:
            raise ImproperlyConfigured(
                f'{cls.__name__}.options_actions: {source_action!r} is neither a CRUD '
                'action nor an @action of the ViewSet.'
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
                f'Options{view_action}{model.__name__}',
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
                f'Options{view_action}{model.__name__}',
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

    def _form_options_create(self, request, *args, **kwargs):
        return self.form_options(request, *args, **kwargs)

    def _form_options_update(self, request, *args, **kwargs):
        return self.form_options(request, *args, **kwargs)

    def _form_options_list(self, request, *args, **kwargs):
        return self.form_options(request, *args, **kwargs)

    def _form_options_custom(self, request, *args, **kwargs):
        return self.form_options(request, *args, **kwargs)


class OptionsModelViewSetMetaclass(type):
    """
    Register the form-options routes when the ViewSet class is created.

    A route is added for each action in ``options_actions`` whose options
    serializer has at least one field, so resources without choices or writable
    relations (or, for ``list``, without a filterset with choice/relation filters)
    get no route. ViewSets without ``GET`` are skipped.
    """

    def __new__(cls, name, bases, attrs):
        klass = super().__new__(cls, name, bases, attrs)
        if not issubclass(klass, viewsets.ModelViewSet):
            return klass
        if 'get' not in [m.lower() for m in klass.http_method_names]:
            return klass

        if not issubclass(klass, OptionsBaseModelMixin):
            raise TypeError(
                'OptionsModelViewSetMetaclass can only be used with '
                'OptionsBaseModelMixin'
            )

        options_routes = (
            (
                'create',
                klass.action_options_create,
                klass.url_path_options_create,
                klass._form_options_create,
                extend_schema_options_create,
            ),
            (
                'update',
                klass.action_options_update,
                klass.url_path_options_update,
                klass._form_options_update,
                extend_schema_options_update,
            ),
            (
                'list',
                klass.action_options_list,
                klass.url_path_options_list,
                klass._form_options_list,
                extend_schema_options_list,
            ),
        )
        custom_routes = cls._get_custom_options_routes(klass)
        options_routes += custom_routes
        cls._remove_inherited_custom_actions(
            klass, attrs, {route[1] for route in custom_routes}
        )
        for (
            source_action,
            action_name,
            url_path,
            handler,
            schema,
            *action_kwargs,
        ) in options_routes:
            serializer_class = None
            if source_action in klass.options_actions:
                serializer_class = cls._get_options_class(klass, action_name)
            if serializer_class is None:
                cls._remove_inherited_action(klass, attrs, action_name)
                continue
            # The action is built here (not declared on the mixin) so that the
            # route only exists when there are fields and uses the class paths.
            view_func = cls._make_options_view(handler, action_name)
            view_func = action(
                detail=False,
                methods=['get'],
                url_path=url_path,
                **(action_kwargs[0] if action_kwargs else {}),
            )(view_func)
            view_func = schema(
                model=serializer_class.Meta.model,
                responses=serializer_class,
                parameters=get_form_options_parameters(
                    serializer_class, search=klass.options_search
                ),
            )(view_func)
            setattr(klass, action_name, view_func)

        return klass

    @staticmethod
    def _get_custom_options_routes(klass) -> tuple:
        """Routes of the custom actions named in ``options_actions``."""
        routes = []
        actions_map = klass.get_options_actions_map()
        for source_action in klass.options_actions:
            if source_action in OPTIONS_CRUD_ACTIONS:
                continue
            func = klass.get_custom_action(source_action)
            if re.compile(func.url_path).groups:
                raise ImproperlyConfigured(
                    f'{klass.__name__}.options_actions: {source_action!r} has URL '
                    f'parameters in its url_path ({func.url_path!r}); its options '
                    'route would require them. Declare the options action manually.'
                )
            if klass.get_custom_options_kind(source_action) == 'list':
                url_path = f'{func.url_path}/{klass.url_path_options_list}'
                schema = extend_schema_options_list
            else:
                url_path = f'form-options-{func.url_path}'
                schema = extend_schema_options_update
            action_kwargs = {}
            permission_classes = func.kwargs.get('permission_classes')
            if permission_classes is not None:
                action_kwargs['permission_classes'] = permission_classes
            routes.append(
                (
                    source_action,
                    actions_map[source_action],
                    url_path,
                    klass._form_options_custom,
                    schema,
                    action_kwargs,
                )
            )
        return tuple(routes)

    @classmethod
    def _remove_inherited_custom_actions(cls, klass, attrs, action_names):
        """
        Record the custom options actions of this class and hide the ones inherited
        from a parent ViewSet that this class no longer lists in ``options_actions``.
        """
        inherited = set()
        for base in klass.__mro__[1:]:
            inherited |= base.__dict__.get('_options_custom_action_names', set())
        for action_name in inherited - action_names:
            cls._remove_inherited_action(klass, attrs, action_name)
        klass._options_custom_action_names = frozenset(action_names)

    @staticmethod
    def _remove_inherited_action(klass, attrs, action_name):
        """
        Hide an options route inherited from a parent ViewSet when this class
        disables it (``options_actions``) or has no options fields. DRF skips
        attributes without an action ``mapping`` when collecting routes.
        """
        if action_name in attrs:
            return
        if getattr(getattr(klass, action_name, None), 'mapping', None) is not None:
            setattr(klass, action_name, None)

    @staticmethod
    def _make_options_view(handler, action_name):
        # DRF maps the HTTP method to the function ``__name__``; it must match the
        # action name so ``self.action`` resolves correctly.
        def view_func(self, request, *args, **kwargs):
            return handler(self, request, *args, **kwargs)

        view_func.__name__ = action_name
        return view_func

    @classmethod
    def _get_options_class(cls, klass, options_action):
        """Return the options serializer class, or ``None`` when it has no fields."""
        try:
            view_obj = klass()
            view_obj.action = options_action
            serializer_class = view_obj.get_options_serializer_class()
            if serializer_class is None:
                return None
            fields = serializer_class({}).get_fields()
        except ImproperlyConfigured:
            raise
        except Exception as exc:
            raise ImproperlyConfigured(
                f'Could not build form options for {klass.__name__}.{options_action}: '
                f'{exc!r}. get_serializer_class() runs without a request when the '
                "class is created; guard it with getattr(self, 'request', None) or "
                'disable the routes with options_actions = ().'
            ) from exc
        if not fields:
            return None
        return serializer_class


class OptionsModelMixin(OptionsBaseModelMixin, metaclass=OptionsModelViewSetMetaclass):
    """Form-options mixin with automatic route registration."""
