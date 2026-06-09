import factory
from factory.django import DjangoModelFactory

from apps.accounts.choices import StoredFileAccess
from apps.accounts.models.files import StoredFile
from apps.generics.factories.mixins import ModelFactoryMixin


class StoredFileFactory(ModelFactoryMixin, DjangoModelFactory):
    file = factory.django.FileField(
        filename='test.txt',
        data=b'Hello, World!',
    )
    name = None
    viewing_permission = StoredFileAccess.OWNER
    updating_permission = StoredFileAccess.OWNER
    owner = factory.SubFactory(
        'apps.accounts.factories.users.UserFactory',
    )
    organization = factory.SubFactory(
        'apps.accounts.factories.organizations.OrganizationFactory',
    )

    class Meta:
        model = StoredFile

    class Params:
        # ─── Permission traits ────────────────────────────────────────
        public = factory.Trait(
            viewing_permission=StoredFileAccess.PUBLIC,
            updating_permission=StoredFileAccess.PUBLIC,
        )
        org_members = factory.Trait(
            viewing_permission=StoredFileAccess.MEMBERS_ORGANIZATION,
            updating_permission=StoredFileAccess.MEMBERS_ORGANIZATION,
        )
        org_managers = factory.Trait(
            viewing_permission=StoredFileAccess.MANAGERS_ORGANIZATION,
            updating_permission=StoredFileAccess.MANAGERS_ORGANIZATION,
        )
        org_admins = factory.Trait(
            viewing_permission=StoredFileAccess.ADMINS_ORGANIZATION,
            updating_permission=StoredFileAccess.ADMINS_ORGANIZATION,
        )
        org_owners = factory.Trait(
            viewing_permission=StoredFileAccess.OWNERS_ORGANIZATION,
            updating_permission=StoredFileAccess.OWNERS_ORGANIZATION,
        )

        # ─── File type traits ─────────────────────────────────────────
        txt = factory.Trait(
            file=factory.django.FileField(
                filename='test.txt',
                data=b'Hello, World!',
            ),
        )
        pdf = factory.Trait(
            file=factory.django.FileField(
                filename='test.pdf',
                data=(
                    b'%PDF-1.4\n'
                    b'1 0 obj\n'
                    b'<< /Type /Catalog /Pages 2 0 R >>\n'
                    b'endobj\n'
                    b'2 0 obj\n'
                    b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n'
                    b'endobj\n'
                    b'3 0 obj\n'
                    b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\n'
                    b'endobj\n'
                    b'trailer\n'
                    b'<< /Root 1 0 R >>\n'
                    b'%%EOF'
                ),
            ),
        )
        png = factory.Trait(
            file=factory.django.FileField(
                filename='test.png',
                data=(
                    b'\x89PNG\r\n\x1a\n'
                    b'\x00\x00\x00\rIHDR'
                    b'\x00\x00\x00\x01'
                    b'\x00\x00\x00\x01'
                    b'\x08'
                    b'\x02'
                    b'\x00\x00\x00\x00'
                    b'\x00\x00\x00\x00IDAT'
                ),
            ),
        )
        jpg = factory.Trait(
            file=factory.django.FileField(
                filename='test.jpg',
                data=(
                    b'\xff\xd8\xff\xe0'
                    b'\x00\x10JFIF\x00\x01'
                    b'\x01\x00\x00\x01\x00\x01\x00\x00'
                    b'\xff\xdb\x00\x43\x00'
                    b'\xff\xc0\x00\x0b\x08\x00\x01'
                    b'\x00\x01\x01\x01\x11\x00'
                    b'\xff\xc4\x00\x1f\x00\x00'
                    b'\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00'
                    b'\x7f\xff\xd9'
                ),
            ),
        )
        gif = factory.Trait(
            file=factory.django.FileField(
                filename='test.gif',
                data=(
                    b'GIF89a'
                    b'\x01\x00\x01\x00'
                    b'\x80'
                    b'\x00'
                    b'\x00\x00\x00\x00\x00'
                    b'\x21\xf9\x04\x00\x00\x00\x00\x00'
                    b'\x2c\x00\x00\x00\x00'
                    b'\x01\x00\x01\x00\x00'
                    b'\x02\x02\x44\x01\x00'
                    b';'
                ),
            ),
        )
        webp = factory.Trait(
            file=factory.django.FileField(
                filename='test.webp',
                data=(
                    b'RIFF'
                    b'\x1a\x00\x00\x00'
                    b'WEBP'
                    b'VP8 '
                    b'\x12\x00\x00\x00'
                    b'\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x00\x00'
                ),
            ),
        )
        svg = factory.Trait(
            file=factory.django.FileField(
                filename='test.svg',
                data=(
                    b'<?xml version="1.0" encoding="UTF-8"?>\n'
                    b'<svg xmlns="http://www.w3.org/2000/svg" '
                    b'width="1" height="1">\n'
                    b'  <rect width="1" height="1" fill="red"/>\n'
                    b'</svg>'
                ),
            ),
        )
        csv = factory.Trait(
            file=factory.django.FileField(
                filename='test.csv',
                data=(
                    b'name,email,role\n'
                    b'John Doe,john@example.com,admin\n'
                    b'Jane Smith,jane@example.com,manager\n'
                    b'Bob Wilson,bob@example.com,member\n'
                ),
            ),
        )
        html = factory.Trait(
            file=factory.django.FileField(
                filename='test.html',
                data=(
                    b'<!DOCTYPE html>\n'
                    b'<html lang="en">\n'
                    b'<head><title>Test</title></head>\n'
                    b'<body>\n'
                    b'  <h1>Hello, World!</h1>\n'
                    b'  <p>This is a test HTML file.</p>\n'
                    b'</body>\n'
                    b'</html>'
                ),
            ),
        )
        json = factory.Trait(
            file=factory.django.FileField(
                filename='test.json',
                data=(
                    b'{\n'
                    b'  "name": "test",\n'
                    b'  "version": 1.0,\n'
                    b'  "enabled": true,\n'
                    b'  "tags": ["a", "b", "c"],\n'
                    b'  "metadata": {\n'
                    b'    "created": "2026-06-01",\n'
                    b'    "author": "test"\n'
                    b'  }\n'
                    b'}'
                ),
            ),
        )
        xml = factory.Trait(
            file=factory.django.FileField(
                filename='test.xml',
                data=(
                    b'<?xml version="1.0" encoding="UTF-8"?>\n'
                    b'<root>\n'
                    b'  <item id="1">\n'
                    b'    <name>Item 1</name>\n'
                    b'    <value>100</value>\n'
                    b'  </item>\n'
                    b'  <item id="2">\n'
                    b'    <name>Item 2</name>\n'
                    b'    <value>200</value>\n'
                    b'  </item>\n'
                    b'</root>'
                ),
            ),
        )
        zip = factory.Trait(
            file=factory.django.FileField(
                filename='test.zip',
                data=(
                    b'PK\x03\x04'
                    b'\x14\x00\x00\x00\x00\x00'
                    b'\x00\x00'
                    b'\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x00\x00\x00\x00'
                    b'\x00\x00\x00\x00'
                    b'\x00\x00'
                    b'\x00\x00'
                ),
            ),
        )
        gz = factory.Trait(
            file=factory.django.FileField(
                filename='archive.tar.gz',
                data=(
                    b'\x1f\x8b\x08\x00'
                    b'\x00\x00\x00\x00'
                    b'\x00\x03'
                    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x00\x00\x00\x00\x00\x00\x00\x00'
                ),
            ),
        )
        no_ext = factory.Trait(
            file=factory.django.FileField(
                filename='test',
                data=b'binary content without file extension',
            ),
        )
        bin_ = factory.Trait(
            file=factory.django.FileField(
                filename='test.bin',
                data=b'\x00\x01\x02\x03\xff\xfe\xfd\xfc\x7f\x80\x81\x82',
            ),
        )
