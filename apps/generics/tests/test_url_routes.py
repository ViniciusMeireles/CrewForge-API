import json
from pathlib import Path

from django.test import SimpleTestCase
from django.urls import URLResolver, get_resolver

SNAPSHOT = Path(__file__).parent / 'data' / 'url_routes.json'


def iter_routes(patterns, prefix='', namespace=''):
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            scope = f'{pattern.namespace}:' if pattern.namespace else ''
            yield from iter_routes(
                pattern.url_patterns,
                prefix + str(pattern.pattern),
                namespace + scope,
            )
            continue
        callback = pattern.callback
        view = getattr(callback, 'cls', None)
        actions = getattr(callback, 'actions', None)
        yield {
            'path': prefix + str(pattern.pattern),
            'name': namespace + (pattern.name or ''),
            'view': view.__name__ if view else callback.__name__,
            'actions': actions
            and {method: name for method, name in actions.items() if method != 'head'},
        }


def route_key(route: dict) -> str:
    return json.dumps(route, sort_keys=True)


class UrlRoutesSnapshotTestCase(SimpleTestCase):
    def test_routes_match_the_snapshot(self):
        patterns = get_resolver().url_patterns
        routes = {route_key(route) for route in iter_routes(patterns)}
        expected = {route_key(route) for route in json.loads(SNAPSHOT.read_text())}
        self.assertEqual(sorted(routes - expected), [])
        self.assertEqual(sorted(expected - routes), [])
