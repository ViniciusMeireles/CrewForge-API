from rest_framework_simplejwt.settings import DEFAULTS as DEFAULTS_BASE
from rest_framework_simplejwt.settings import IMPORT_STRINGS, USER_SETTINGS, APISettings

DEFAULTS = DEFAULTS_BASE
DEFAULTS.update(
    {
        'TOKEN_OBTAIN_SERIALIZER': 'apps.accounts.serializers.auth.'
        'TokenObtainPairSerializer',
    }
)


jwt_settings = APISettings(USER_SETTINGS, DEFAULTS, IMPORT_STRINGS)
