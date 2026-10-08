from .base import *  # noqa
from .base import REST_FRAMEWORK, SECRET_KEY, SIMPLE_JWT
from .checks import require_num_proxies, require_production_secrets

DEBUG = False

require_production_secrets(SECRET_KEY, SIMPLE_JWT)
require_num_proxies(REST_FRAMEWORK)
