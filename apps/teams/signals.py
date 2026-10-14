from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.accounts.models.member import Member
from apps.teams.models.team_member import TeamMember


@receiver(post_save, sender=Member)
def end_team_memberships_of_removed_member(sender, instance, **kwargs):
    """A removed member leaves every team, so readmission starts without teams."""
    if instance.is_active:
        return
    TeamMember.objects.filter(member=instance, is_active=True).update(
        is_active=False,
        updated_at=timezone.now(),
    )
