from .base import *  # noqa
from .base import SECRET_KEY, SIMPLE_JWT
from .checks import require_production_secrets

DEBUG = False

require_production_secrets(SECRET_KEY, SIMPLE_JWT)
