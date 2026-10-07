from .base import *  # noqa
from .base import SECRET_KEY, SIMPLE_JWT
from .checks import require_secret

DEBUG = False

require_secret('DJANGO_SECRET_KEY', SECRET_KEY)
if 'SIGNING_KEY' in SIMPLE_JWT:
    require_secret('JWT_SIGNING_KEY', SIMPLE_JWT['SIGNING_KEY'])
