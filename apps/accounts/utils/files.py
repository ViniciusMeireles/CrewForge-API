import mimetypes

from django.conf import settings
from django.core.files.uploadhandler import FileUploadHandler, StopUpload
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

TEXT = 'text'
SNIFF_SIZE = 2048
UPLOAD_REQUEST_OVERHEAD = 1024 * 1024
ALLOWED_CONTROL_BYTES = frozenset(b'\t\n\r\x0c')

BINARY_SIGNATURES = (
    (b'\x89PNG\r\n\x1a\n', 'image/png'),
    (b'\xff\xd8\xff', 'image/jpeg'),
    (b'GIF87a', 'image/gif'),
    (b'GIF89a', 'image/gif'),
    (b'%PDF-', 'application/pdf'),
    (b'PK\x03\x04', 'application/zip'),
    (b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1', 'application/x-ole-storage'),
)

CONTAINER_TYPES = {
    'application/zip': {
        'application/zip',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'application/vnd.oasis.opendocument.text',
        'application/vnd.oasis.opendocument.spreadsheet',
        'application/vnd.oasis.opendocument.presentation',
    },
    'application/x-ole-storage': {
        'application/msword',
        'application/vnd.ms-excel',
        'application/vnd.ms-powerpoint',
    },
}
TEXT_DATA_TYPES = frozenset({'application/json'})


def sniff_content_type(file) -> str | None:
    """Detect the type from the file bytes; ``TEXT`` for UTF-8 or Windows-1252 text."""
    file.seek(0)
    head = file.read(SNIFF_SIZE)
    file.seek(0)
    for signature, content_type in BINARY_SIGNATURES:
        if head.startswith(signature):
            return content_type
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'image/webp'
    if any(byte < 0x20 and byte not in ALLOWED_CONTROL_BYTES for byte in head):
        return None
    for trim in range(4):
        try:
            head[: len(head) - trim].decode('utf-8')
        except UnicodeDecodeError:
            continue
        return TEXT
    try:
        head.decode('cp1252')
    except UnicodeDecodeError:
        return None
    return TEXT


def _resolve(sniffed: str | None, guessed: str | None) -> str | None:
    """Combine the sniffed and guessed types; ``None`` when they disagree."""
    if sniffed == TEXT:
        if guessed is None:
            return 'text/plain'
        if guessed.startswith('text/') or guessed in TEXT_DATA_TYPES:
            return guessed
        return None
    if sniffed in CONTAINER_TYPES:
        return guessed if guessed in CONTAINER_TYPES[sniffed] else None
    if sniffed and guessed in (None, sniffed):
        return sniffed
    return None


def content_type_for(file) -> str:
    """Best-effort type of a stored file: bytes first, then the file name."""
    guessed, __ = mimetypes.guess_type(file.name.split('/')[-1])
    try:
        sniffed = sniff_content_type(file)
    except OSError, ValueError:
        sniffed = None
    return _resolve(sniffed, guessed) or guessed or 'application/octet-stream'


def detect_upload_content_type(file, allowed_types) -> str:
    """Return the validated content type of an upload or raise ``ValidationError``."""
    if file.size > settings.STORED_FILE_MAX_SIZE:
        raise serializers.ValidationError(
            file_too_large_error(path=()).detail, code='file_too_large'
        )

    guessed, __ = mimetypes.guess_type(file.name.split('/')[-1])
    content_type = _resolve(sniff_content_type(file), guessed)
    if content_type not in allowed_types:
        raise serializers.ValidationError(
            _('This file type is not allowed.'),
            code='file_type_not_allowed',
        )
    return content_type


def is_inline_content_type(content_type: str | None) -> bool:
    return content_type in settings.STORED_FILE_INLINE_CONTENT_TYPES


def max_upload_request_size() -> int:
    return settings.STORED_FILE_MAX_SIZE + UPLOAD_REQUEST_OVERHEAD


def file_too_large_error(path=('file',)) -> serializers.ValidationError:
    detail = [
        _('The file is too large. Maximum size is %(size)s MB.')
        % {'size': settings.STORED_FILE_MAX_SIZE // (1024 * 1024)}
    ]
    for key in reversed(path):
        detail = {key: detail}
    return serializers.ValidationError(detail, code='file_too_large')


def upload_too_large(request) -> bool:
    return bool(getattr(request, 'upload_too_large', False))


class MaxSizeUploadHandler(FileUploadHandler):
    """Stop storing an upload as soon as it exceeds ``STORED_FILE_MAX_SIZE``."""

    def new_file(self, *args, **kwargs):
        super().new_file(*args, **kwargs)
        self.received = 0

    def receive_data_chunk(self, raw_data, start):
        self.received += len(raw_data)
        if self.received > settings.STORED_FILE_MAX_SIZE:
            if self.request is not None:
                self.request.upload_too_large = True
            raise StopUpload(connection_reset=False)
        return raw_data

    def file_complete(self, file_size):
        return None
