import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_var: ContextVar[str] = ContextVar('request_id', default='')

_STANDARD_ATTRIBUTES = set(logging.LogRecord('', 0, '', 0, '', (), None).__dict__) | {
    'message',
    'asctime',
    'request_id',
    'request',
}


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or getattr(
            getattr(record, 'request', None), 'request_id', ''
        )
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per record: standard fields plus any ``extra`` attributes."""

    def format(self, record: logging.LogRecord) -> str:
        data = {
            'timestamp': datetime.fromtimestamp(record.created, UTC).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'request_id': getattr(record, 'request_id', ''),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRIBUTES and not key.startswith('_'):
                data.setdefault(key, value)
        if record.exc_info:
            data['exception'] = self.formatException(record.exc_info)
        return json.dumps(data, default=str)
