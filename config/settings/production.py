import os

from .base import *  # noqa
from .base import MEDIA_ROOT, REST_FRAMEWORK, SECRET_KEY, SIMPLE_JWT
from .checks import require_media_root, require_num_proxies, require_production_secrets
from .observability import init_sentry

DEBUG = False

require_production_secrets(SECRET_KEY, SIMPLE_JWT)
require_num_proxies(REST_FRAMEWORK)
require_media_root(MEDIA_ROOT)
init_sentry(os.environ)
