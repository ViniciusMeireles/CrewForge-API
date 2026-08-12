from http import HTTPMethod
from typing import Any, Literal, Sequence

from rest_framework.decorators import action

from apps.generics.utils.filters import orderable_filter_factory


def _build_orderable_filter_class(
    filterset_class,
    serializer_class,
):
    if not (filterset_class and serializer_class):
        return filterset_class
    return orderable_filter_factory(
        serializer_class=serializer_class,
        filterset_class=filterset_class,
    )


def action_custom(
    *,
    detail: bool,
    methods: Sequence[
        Literal[
            'GET',
            'POST',
            'DELETE',
            'PUT',
            'PATCH',
            'TRACE',
            'HEAD',
            'OPTIONS',
            'get',
            'post',
            'delete',
            'put',
            'patch',
            'trace',
            'head',
            'options',
        ]
        | HTTPMethod
    ]
    | None = None,
    url_path: str | None = None,
    url_name: str | None = None,
    auto_orderable_filter: bool | None = None,
    **kwargs: Any,
):
    if auto_orderable_filter:
        kwargs['filterset_class'] = _build_orderable_filter_class(
            filterset_class=kwargs.get('filterset_class'),
            serializer_class=kwargs.get('serializer_class'),
        )
    return action(
        detail=detail,
        methods=methods,
        url_path=url_path,
        url_name=url_name,
        **kwargs,
    )
