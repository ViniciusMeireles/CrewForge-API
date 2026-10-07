import mimetypes

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

TEXT = 'text'
SNIFF_SIZE = 2048

BINARY_SIGNATURES = (
    (b'\x89PNG\r\n\x1a\n', 'image/png'),
    (b'\xff\xd8\xff', 'image/jpeg'),
    (b'GIF87a', 'image/gif'),
    (b'GIF89a', 'image/gif'),
    (b'%PDF-', 'application/pdf'),
)


def sniff_content_type(file) -> str | None:
    """Detect the type from the file bytes; ``TEXT`` for UTF-8 text without NUL."""
    file.seek(0)
    head = file.read(SNIFF_SIZE)
    file.seek(0)
    for signature, content_type in BINARY_SIGNATURES:
        if head.startswith(signature):
            return content_type
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'image/webp'
    if b'\x00' in head:
        return None
    for trim in range(4):
        try:
            head[: len(head) - trim].decode('utf-8')
        except UnicodeDecodeError:
            continue
        return TEXT
    return None


def detect_upload_content_type(file, allowed_types) -> str:
    """Return the validated content type of an upload or raise ``ValidationError``."""
    if file.size > settings.STORED_FILE_MAX_SIZE:
        raise serializers.ValidationError(
            _('The file is too large. Maximum size is %(size)s MB.')
            % {'size': settings.STORED_FILE_MAX_SIZE // (1024 * 1024)},
            code='file_too_large',
        )

    sniffed = sniff_content_type(file)
    guessed, __ = mimetypes.guess_type(file.name.split('/')[-1])
    if sniffed == TEXT:
        content_type = guessed or 'text/plain'
        if not content_type.startswith('text/'):
            content_type = None
    elif sniffed and guessed in (None, sniffed):
        content_type = sniffed
    else:
        content_type = None

    if content_type not in allowed_types:
        raise serializers.ValidationError(
            _('This file type is not allowed.'),
            code='file_type_not_allowed',
        )
    return content_type


def is_inline_content_type(content_type: str | None) -> bool:
    return content_type in settings.STORED_FILE_INLINE_CONTENT_TYPES
