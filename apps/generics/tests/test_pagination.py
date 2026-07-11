from django.test import SimpleTestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.generics.pagination import CustomPageNumberPagination

factory = APIRequestFactory()


class CustomPageNumberPaginationTestCase(SimpleTestCase):
    def setUp(self):
        self.paginator = CustomPageNumberPagination()
        self.queryset = list(range(200))

    def _paginate(self, query_params=''):
        url = f'/?{query_params}' if query_params else '/'
        request = Request(factory.get(url))
        page = self.paginator.paginate_queryset(self.queryset, request)
        return page, request

    def test_default_page_size(self):
        page, _ = self._paginate()
        self.assertEqual(len(page), 10)

    def test_custom_page_size(self):
        page, _ = self._paginate('page_size=50')
        self.assertEqual(len(page), 50)

    def test_page_size_exceeds_max(self):
        page, _ = self._paginate('page_size=999')
        self.assertEqual(len(page), 100)

    def test_page_size_zero(self):
        page, _ = self._paginate('page_size=0')
        self.assertEqual(len(page), 10)

    def test_page_size_negative(self):
        page, _ = self._paginate('page_size=-5')
        self.assertEqual(len(page), 10)

    def test_page_size_non_numeric(self):
        page, _ = self._paginate('page_size=abc')
        self.assertEqual(len(page), 10)

    def test_next_url_preserves_page_size(self):
        _, request = self._paginate('page_size=50')
        next_url = self.paginator.get_next_link()
        self.assertIn('page_size=50', next_url)

    def test_page_size_with_page_parameter(self):
        page, _ = self._paginate('page=2&page_size=25')
        self.assertEqual(len(page), 25)
        self.assertEqual(page[0], 25)
