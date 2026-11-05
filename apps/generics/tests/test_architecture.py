import ast
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

APPS_DIR = Path(settings.BASE_DIR) / 'apps'
SERVICE_BACKED_VIEWS = (
    'accounts/views/auth.py',
    'accounts/views/invitations.py',
    'accounts/views/members.py',
    'accounts/views/organizations.py',
    'accounts/views/signup.py',
    'accounts/views/user_profile.py',
    'teams/views/team_members.py',
    'teams/views/teams.py',
)
SERVICE_BACKED_SERIALIZERS = (
    'accounts/serializers/invitation.py',
    'accounts/serializers/member.py',
    'accounts/serializers/organization.py',
    'accounts/serializers/organization_image.py',
    'accounts/serializers/signup.py',
    'accounts/serializers/user_profile.py',
    'teams/serializers/team.py',
    'teams/serializers/team_member.py',
)
VIEW_FORBIDDEN = ('transaction', 'record_audit_event')
SERIALIZER_FORBIDDEN = (*VIEW_FORBIDDEN, 'log_security_event', 'send_verification')


def module_name(path: Path) -> str:
    relative = path.relative_to(APPS_DIR.parent).with_suffix('')
    parts = relative.parts[:-1] if relative.name == '__init__' else relative.parts
    return '.'.join(parts)


def source_files() -> list[Path]:
    return [
        path
        for path in APPS_DIR.rglob('*.py')
        if not {'tests', 'migrations', 'factories'} & set(path.parts)
    ]


def module_imports(path: Path, modules: set[str]) -> set[str]:
    found = set()
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
            found |= {f'{node.module}.{alias.name}' for alias in node.names}
    return found & modules


def find_cycle(graph: dict[str, set[str]]) -> list[str]:
    done: set[str] = set()

    def visit(module: str, trail: list[str]) -> list[str]:
        if module in trail:
            return [*trail[trail.index(module) :], module]
        if module in done:
            return []
        for imported in sorted(graph[module]):
            if cycle := visit(imported, [*trail, module]):
                return cycle
        done.add(module)
        return []

    for module in sorted(graph):
        if cycle := visit(module, []):
            return cycle
    return []


class ArchitectureTestCase(SimpleTestCase):
    def test_service_backed_modules_leave_writes_to_services(self):
        layers = (
            (SERVICE_BACKED_VIEWS, VIEW_FORBIDDEN),
            (SERVICE_BACKED_SERIALIZERS, SERIALIZER_FORBIDDEN),
        )
        for modules, forbidden in layers:
            for relative in modules:
                source = (APPS_DIR / relative).read_text()
                for name in forbidden:
                    with self.subTest(module=relative, name=name):
                        self.assertNotIn(name, source)

    def test_permission_classes_decide_through_the_access_policy(self):
        for path in APPS_DIR.glob('*/permissions/*.py'):
            if path.parts[-3] == 'platform':
                continue
            with self.subTest(path=path):
                self.assertNotRegex(
                    path.read_text(), r'\.has_\w+_(permission|access)\b(?!\()'
                )

    def test_no_module_level_import_cycles(self):
        files = {module_name(path): path for path in source_files()}
        modules = set(files)
        graph = {
            name: module_imports(path, modules) - {name} for name, path in files.items()
        }
        self.assertEqual(find_cycle(graph), [])

    def test_models_are_imported_explicitly(self):
        for path in APPS_DIR.glob('*/models/__init__.py'):
            with self.subTest(path=path):
                self.assertNotIn('listdir', path.read_text())

    def test_find_cycle_reports_a_cycle(self):
        graph = {'a': {'b'}, 'b': {'a'}, 'c': set()}
        self.assertEqual(find_cycle(graph), ['a', 'b', 'a'])
