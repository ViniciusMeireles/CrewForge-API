from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.choices import OrganizationImageTypeChoices
from apps.accounts.factories.organization_image import OrganizationImageFactory
from apps.accounts.factories.organizations import (
    OrganizationProfileFactory,
)
from apps.accounts.models.organization import OrganizationImage


class OrganizationImageModelTestCase(TestCase):
    def test_str(self):
        image = OrganizationImageFactory()
        expected = f'{image.profile} - {image.image_type}'
        self.assertEqual(str(image), expected)

    def test_label_expression(self):
        image = OrganizationImageFactory()
        expr = OrganizationImage.label_expression()
        queryset = OrganizationImage.objects.filter(id=image.id).annotate(label=expr)
        self.assertEqual(queryset.first().label, image.image_type)

    def test_filter_actives_image_inactive(self):
        OrganizationImageFactory(image__is_active=False)
        self.assertEqual(OrganizationImage.objects.filter_actives().count(), 0)

    def test_filter_actives_profile_inactive(self):
        OrganizationImageFactory(profile__is_active=False)
        self.assertEqual(OrganizationImage.objects.filter_actives().count(), 0)

    def test_filter_actives_organization_inactive(self):
        OrganizationImageFactory(profile__organization__is_active=False)
        self.assertEqual(OrganizationImage.objects.filter_actives().count(), 0)

    def test_filter_actives_self_inactive(self):
        OrganizationImageFactory(is_active=False)
        self.assertEqual(OrganizationImage.objects.filter_actives().count(), 0)

    def test_unique_constraint_same_profile_and_type(self):
        profile = OrganizationProfileFactory()
        OrganizationImageFactory(
            profile=profile, image_type=OrganizationImageTypeChoices.LOGO
        )
        with self.assertRaises(IntegrityError):
            OrganizationImageFactory(
                profile=profile, image_type=OrganizationImageTypeChoices.LOGO
            )

    def test_unique_constraint_different_profile_same_type(self):
        OrganizationImageFactory(image_type=OrganizationImageTypeChoices.LOGO)
        OrganizationImageFactory(image_type=OrganizationImageTypeChoices.LOGO)
        self.assertEqual(
            OrganizationImage.objects.filter(
                image_type=OrganizationImageTypeChoices.LOGO
            ).count(),
            2,
        )

    def test_unique_constraint_same_profile_different_type(self):
        profile = OrganizationProfileFactory()
        OrganizationImageFactory(
            profile=profile, image_type=OrganizationImageTypeChoices.LOGO
        )
        OrganizationImageFactory(
            profile=profile, image_type=OrganizationImageTypeChoices.COVER
        )
        self.assertEqual(OrganizationImage.objects.filter(profile=profile).count(), 2)

    def test_cascade_profile_delete(self):
        image = OrganizationImageFactory()
        profile = image.profile
        profile.delete()
        self.assertFalse(OrganizationImage.objects.filter(id=image.id).exists())

    def test_cascade_image_delete(self):
        image = OrganizationImageFactory()
        stored_file = image.image
        stored_file.delete()
        self.assertFalse(OrganizationImage.objects.filter(id=image.id).exists())
