from django.conf import settings
from django.utils.cache import patch_vary_headers
from django.utils.translation import get_language, get_supported_language_variant
from drf_spectacular.plumbing import set_query_parameters
from drf_spectacular.views import SpectacularSwaggerView

LOCALE_COOKIE = 'cf_locale'
LOCALE_COOKIE_VALUES = {'en': 'en-US', 'pt-br': 'pt-BR'}


def resolve_docs_language(request) -> str:
    for candidate in (request.GET.get('lang'), request.COOKIES.get(LOCALE_COOKIE)):
        if not candidate:
            continue
        try:
            return get_supported_language_variant(candidate.lower())
        except LookupError:
            continue
    return get_supported_language_variant(get_language() or settings.LANGUAGE_CODE)


class ApiDocsView(SpectacularSwaggerView):
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        language = resolve_docs_language(request)
        response.data['docs_lang'] = language
        response.data['sort_tags'] = settings.API_DOCS_SORT_TAGS
        response.data['languages'] = [
            {'code': code, 'name': name, 'locale': LOCALE_COOKIE_VALUES.get(code, code)}
            for code, name in settings.LANGUAGES
        ]
        response.data['schema_url'] = set_query_parameters(
            response.data['schema_url'], lang=language
        )
        patch_vary_headers(response, ['Cookie'])
        return response
