from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.generics.models.abstracts import BaseModel
from apps.teams.choices import TeamMemberRoleChoices
from apps.teams.managers.team import TeamManager


class Team(BaseModel):
    name = models.CharField(
        max_length=100, verbose_name=_('Name'), help_text=_('Name of the team')
    )
    slug = models.SlugField(verbose_name=_('Slug'), help_text=_('Team slug'))
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Description of the team'),
    )
    organization = models.ForeignKey(
        to='accounts.Organization',
        on_delete=models.CASCADE,
        related_name='teams',
        verbose_name=_('Organization'),
        help_text=_('Organization to which the team belongs'),
    )

    objects = TeamManager()

    class Meta:
        ordering = ['-id']
        verbose_name = _('Team')
        verbose_name_plural = _('Teams')
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'organization'],
                name='unique_name_org_when_active',
                condition=models.Q(is_active=True),
                violation_error_message=_('This team already exists.'),
            ),
            models.UniqueConstraint(
                fields=['slug', 'organization'],
                name='unique_slug_org_when_active',
                condition=models.Q(is_active=True),
                violation_error_message=_('This team already exists.'),
            ),
        ]

    def __str__(self):
        return self.name

    def get_active_team_member(self, member):
        """Active membership of ``member`` in this team, or ``None``."""
        if member is None:
            return None
        return self.members.filter(
            member_id=member.id,
            is_active=True,
            member__is_active=True,
        ).first()

    def can_manage_members(self, member) -> bool:
        """Organization manager+ or the team owner/admin."""
        return bool(TeamMemberRoleChoices.assignable_by(member, self))
