from collections import Counter

from django.test import SimpleTestCase
from django.utils import translation
from drf_spectacular.generators import SchemaGenerator

HTTP_METHODS = {'get', 'post', 'put', 'patch', 'delete'}
LANGUAGES = ('en', 'pt-br')


def get_operations(language: str) -> list[tuple[str, str, dict]]:
    with translation.override(language):
        schema = SchemaGenerator().get_schema(request=None, public=True)
    return [
        (method, path, operation)
        for path, operations in schema['paths'].items()
        for method, operation in operations.items()
        if method in HTTP_METHODS
    ]


class OperationSummaryTestCase(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.operations = {language: get_operations(language) for language in LANGUAGES}

    def test_every_operation_has_a_short_summary(self):
        for language, operations in self.operations.items():
            for method, path, operation in operations:
                with self.subTest(language=language, method=method, path=path):
                    summary = str(operation.get('summary') or '')
                    self.assertTrue(summary)
                    self.assertFalse(summary.endswith('.'))

    def test_summary_differs_from_description(self):
        for language, operations in self.operations.items():
            for method, path, operation in operations:
                with self.subTest(language=language, method=method, path=path):
                    description = str(operation.get('description') or '')
                    self.assertNotEqual(
                        str(operation['summary']), description.rstrip('.')
                    )

    def test_summaries_are_unique_within_a_tag(self):
        for language, operations in self.operations.items():
            with self.subTest(language=language):
                counts = Counter(
                    (str(operation['tags'][0]), str(operation['summary']))
                    for _, _, operation in operations
                )
                duplicates = [key for key, count in counts.items() if count > 1]
                self.assertEqual(duplicates, [])

    def test_generic_summary_uses_lowercase_model_name(self):
        expected = {'en': 'List teams', 'pt-br': 'Listar equipes'}
        for language, operations in self.operations.items():
            with self.subTest(language=language):
                summary = next(
                    operation['summary']
                    for method, path, operation in operations
                    if method == 'get' and path == '/api/teams/teams/'
                )
                self.assertEqual(str(summary), expected[language])
