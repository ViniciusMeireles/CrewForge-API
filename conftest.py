import pytest
from django.conf import settings
from django.utils import translation


@pytest.fixture(autouse=True)
def _reset_language():
    translation.activate(settings.LANGUAGE_CODE)
    yield
    translation.deactivate()
