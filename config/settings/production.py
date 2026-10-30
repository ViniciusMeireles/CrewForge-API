import os

from .base import *  # noqa
from .base import MEDIA_ROOT, REST_FRAMEWORK, SECRET_KEY, SIMPLE_JWT
from .checks import require_media_root, require_num_proxies, require_production_secrets
from .observability import init_sentry

DEBUG = False

# HSTS preload is a commitment to the browsers' list that the operator opts into
# per domain (SECURE_HSTS_PRELOAD); it is not a default of the image.
SILENCED_SYSTEM_CHECKS = ['security.W021']

require_production_secrets(SECRET_KEY, SIMPLE_JWT)
require_num_proxies(REST_FRAMEWORK)
require_media_root(MEDIA_ROOT)
init_sentry(os.environ)
