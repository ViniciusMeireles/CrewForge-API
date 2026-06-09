from django.test import TestCase

from apps.accounts.choices import OrganizationImageTypeChoices


class OrganizationImageTypeChoicesTestCase(TestCase):
    def test_enum_values_count(self):
        values = list(OrganizationImageTypeChoices.values)
        self.assertEqual(len(values), 8)

    def test_enum_values(self):
        self.assertEqual(OrganizationImageTypeChoices.LOGO, 'logo')
        self.assertEqual(OrganizationImageTypeChoices.COVER, 'cover')
        self.assertEqual(OrganizationImageTypeChoices.FAVICON, 'favicon')
        self.assertEqual(OrganizationImageTypeChoices.OG_IMAGE, 'og_image')
        self.assertEqual(
            OrganizationImageTypeChoices.LOGO_HORIZONTAL, 'logo_horizontal'
        )
        self.assertEqual(OrganizationImageTypeChoices.LOGO_VERTICAL, 'logo_vertical')
        self.assertEqual(OrganizationImageTypeChoices.LOGO_DARK, 'logo_dark')
        self.assertEqual(OrganizationImageTypeChoices.LOGO_LIGHT, 'logo_light')

    def test_enum_labels(self):
        self.assertEqual(str(OrganizationImageTypeChoices.LOGO.label), 'Logo')
        self.assertEqual(str(OrganizationImageTypeChoices.COVER.label), 'Cover')
        self.assertEqual(str(OrganizationImageTypeChoices.FAVICON.label), 'Favicon')
        self.assertEqual(
            str(OrganizationImageTypeChoices.OG_IMAGE.label), 'Open Graph Image'
        )
        self.assertEqual(
            str(OrganizationImageTypeChoices.LOGO_HORIZONTAL.label), 'Logo Horizontal'
        )
        self.assertEqual(
            str(OrganizationImageTypeChoices.LOGO_VERTICAL.label), 'Logo Vertical'
        )
        self.assertEqual(str(OrganizationImageTypeChoices.LOGO_DARK.label), 'Logo Dark')
        self.assertEqual(
            str(OrganizationImageTypeChoices.LOGO_LIGHT.label), 'Logo Light'
        )
