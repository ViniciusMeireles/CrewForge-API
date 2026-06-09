from django.conf import settings
from django.db import models
from django.db.models.expressions import Case, Value, When
from django.db.models.functions import Concat
from django.utils.translation import gettext_lazy as _

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.managers.member import MemberManager
from apps.generics.models.abstracts import BaseModel


class Member(BaseModel):
    nickname = models.CharField(
        max_length=100,
        verbose_name=_('Nickname'),
        help_text=_('Nickname of the user in the organization'),
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='members',
        verbose_name=_('User'),
        help_text=_('User that is a member of the team'),
    )
    organization = models.ForeignKey(
        to='accounts.Organization',
        on_delete=models.CASCADE,
        related_name='members',
        verbose_name=_('Organization'),
        help_text=_('Organization to which the user belongs'),
    )
    role = models.CharField(
        max_length=20,
        choices=MemberRoleChoices.choices,
        default=MemberRoleChoices.MEMBER,
        verbose_name=_('Role'),
        help_text=_('User role in the organization'),
    )

    objects = MemberManager()

    class Meta:
        ordering = ['-id']
        verbose_name = _('Member')
        verbose_name_plural = _('Members')
        unique_together = [['user', 'organization'], ['nickname', 'organization']]

    def __str__(self):
        return f'{self.user} - {self.organization}'

    @property
    def is_owner(self) -> bool:
        return self.role == MemberRoleChoices.OWNER and self.is_active

    @property
    def is_admin(self) -> bool:
        return self.role == MemberRoleChoices.ADMIN and self.is_active

    @property
    def is_manager(self) -> bool:
        return self.role == MemberRoleChoices.MANAGER and self.is_active

    @property
    def is_member(self) -> bool:
        return self.role == MemberRoleChoices.MEMBER and self.is_active

    @property
    def has_owner_permission(self) -> bool:
        if not self.is_active:
            return False
        return self.is_owner or self.user.is_superuser

    @property
    def has_admin_permission(self) -> bool:
        return self.is_admin or self.has_owner_permission

    @property
    def has_manager_permission(self) -> bool:
        return self.is_manager or self.has_admin_permission

    @property
    def has_member_permission(self) -> bool:
        return self.is_member or self.has_manager_permission

    @classmethod
    def label_expression(
        cls, outer_ref: str | None = None
    ) -> models.expressions.Combinable:
        """
        Define the label expression for the member model.
        This is used to generate the label of the member based on
        the nickname, first name, and last name.
        """
        full_name = f'{outer_ref}__user__full_name' if outer_ref else 'user__full_name'
        nickname = f'{outer_ref}__nickname' if outer_ref else 'nickname'
        role = f'{outer_ref}__role' if outer_ref else 'role'
        label_expression = Case(
            When(
                condition=models.Q(
                    ~models.Q(**{full_name: ''}),
                    ~models.Q(**{nickname: ''}),
                    **{f'{full_name}__isnull': False},
                    **{f'{nickname}__isnull': False},
                ),
                then=Concat(
                    full_name,
                    Value('('),
                    nickname,
                    Value(')'),
                ),
            ),
            When(
                condition=models.Q(
                    ~models.Q(**{full_name: ''}),
                    **{f'{full_name}__isnull': False},
                ),
                then=full_name,
            ),
            When(
                condition=models.Q(
                    ~models.Q(**{nickname: ''}),
                    **{f'{nickname}__isnull': False},
                ),
                then=nickname,
            ),
            default=models.F(role),
            output_field=models.CharField(),
        )
        return label_expression
