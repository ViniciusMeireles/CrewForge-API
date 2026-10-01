from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import filterset
from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.generics.serializers.options import OptionsModelSerializer, OptionsSerializer
from apps.generics.utils.filters import orderable_filter_factory
from apps.generics.utils.models import get_verbose_name
from apps.generics.utils.schema import (
    extend_schema_options_create,
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


OPTIONS_SERIALIZER_DESCRIPTIONS = {
    'create': _('Form options to create a {name}.'),
    'update': _('Form options to update a {name}.'),
}


class OptionsBaseModelMixin:
    """
    Runtime behavior of the form-options endpoints.

    ``GET form-options-create/`` and ``GET form-options-update/`` describe the
    selectable fields (choices and writable relations) of the serializer the
    ViewSet uses for ``create`` and ``update``. The routes themselves are
    registered by ``OptionsModelViewSetMetaclass``.

    ViewSet attributes:

    - ``options_actions``: CRUD actions that get an options route; ``()`` disables
      them (use it when a relation points to a model without organization scope).
    - ``options_serializer_class``: base class of the generated options
      serializer; defines how relation querysets are scoped.
    - ``url_path_options_*`` / ``action_options_*``: route path and action name.
    """

    url_path_options_create = 'form-options-create'
    url_path_options_update = 'form-options-update'
    action_options_create = 'form_options_create'
    action_options_update = 'form_options_update'
    options_actions = ('create', 'update')
    options_serializer_class = OptionsModelSerializer

    @classmethod
    def get_options_actions_map(cls) -> dict[str, str]:
        """Map each CRUD action to its options action name."""
        return {
            'create': cls.action_options_create,
            'update': cls.action_options_update,
        }

    @classmethod
    def get_options_actions_inverse_map(cls) -> dict[str, str]:
        return {v: k for k, v in cls.get_options_actions_map().items()}

    @classmethod
    def _get_options_serializer_class(cls, serializer_class, view_action):
        """
        Build (once per ViewSet) the options serializer for a source serializer.

        The generated ``Meta`` inherits the source ``Meta`` (model, fields,
        read_only_fields, extra_kwargs) and keeps a reference to the source in
        ``Meta.serializer_class``, which ``OptionsModelSerializer`` uses to
        respect the source declared fields.
        """
        if issubclass(serializer_class, OptionsSerializer):
            return serializer_class
        cache = cls.__dict__.get('_options_serializer_class_cache')
        if cache is None:
            cache = {}
            cls._options_serializer_class_cache = cache
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
            description = OPTIONS_SERIALIZER_DESCRIPTIONS.get(view_action.lower())
            if description is not None:
                options_class = extend_schema_serializer(
                    description=format_lazy(description, name=get_verbose_name(model))
                )(options_class)
            cache[key] = options_class
        return cache[key]

    def get_options_serializer_class(self):
        """
        Resolve the options serializer for the current options action.

        ``self.action`` is temporarily switched to the mapped CRUD action so the
        ViewSet's own ``get_serializer_class`` override picks the same serializer
        the write endpoint uses (e.g. ``TeamMemberUpdateSerializer`` for update).
        """
        options_action = self.action
        source_action = self.get_options_actions_inverse_map()[options_action]
        self.action = source_action
        try:
            serializer_class = self.get_serializer_class()
        finally:
            self.action = options_action
        return self._get_options_serializer_class(
            serializer_class=serializer_class,
            view_action=source_action.title(),
        )

    def form_options(self, request, *args, **kwargs):
        """Render the options; fields ignore the (empty) instance."""
        serializer_class = self.get_options_serializer_class()
        serializer = serializer_class({}, context=self.get_serializer_context())
        return Response(serializer.to_representation({}))

    def _form_options_create(self, request, *args, **kwargs):
        return self.form_options(request, *args, **kwargs)

    def _form_options_update(self, request, *args, **kwargs):
        return self.form_options(request, *args, **kwargs)


class OptionsModelViewSetMetaclass(type):
    """
    Register the form-options routes when the ViewSet class is created.

    A route is added for each action in ``options_actions`` whose options
    serializer has at least one field, so resources without choices or writable
    relations get no route. ViewSets without ``GET`` are skipped.
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
        )
        for source_action, action_name, url_path, handler, schema in options_routes:
            serializer_class = None
            if source_action in klass.options_actions:
                serializer_class = cls._get_options_class(klass, action_name)
            if serializer_class is None:
                cls._remove_inherited_action(klass, attrs, action_name)
                continue
            # The action is built here (not declared on the mixin) so that the
            # route only exists when there are fields and uses the class paths.
            view_func = cls._make_options_view(handler, action_name)
            view_func = action(detail=False, methods=['get'], url_path=url_path)(
                view_func
            )
            view_func = schema(
                model=serializer_class.Meta.model,
                responses=serializer_class,
                parameters=get_form_options_parameters(serializer_class),
            )(view_func)
            setattr(klass, action_name, view_func)

        return klass

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
        view_obj = klass()
        view_obj.action = options_action
        serializer_class = view_obj.get_options_serializer_class()
        if not serializer_class({}).get_fields():
            return None
        return serializer_class


class OptionsModelMixin(OptionsBaseModelMixin, metaclass=OptionsModelViewSetMetaclass):
    """Form-options mixin with automatic route registration."""
