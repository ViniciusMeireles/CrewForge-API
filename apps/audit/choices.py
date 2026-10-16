from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditActionChoices(models.TextChoices):
    ORGANIZATION_CREATED = 'organization.created', _('Organization created')
    ORGANIZATION_UPDATED = 'organization.updated', _('Organization updated')
    ORGANIZATION_DELETED = 'organization.deleted', _('Organization deleted')
    ORGANIZATION_LOGIN = 'organization.login', _('Organization accessed')
    ORGANIZATION_PROFILE_UPDATED = (
        'organization.profile.updated',
        _('Organization profile updated'),
    )
    ORGANIZATION_IMAGE_CREATED = (
        'organization.image.created',
        _('Organization image added'),
    )
    ORGANIZATION_IMAGE_UPDATED = (
        'organization.image.updated',
        _('Organization image updated'),
    )
    ORGANIZATION_IMAGE_DELETED = (
        'organization.image.deleted',
        _('Organization image removed'),
    )
    MEMBER_JOINED = 'member.joined', _('Member joined')
    MEMBER_READMITTED = 'member.readmitted', _('Member readmitted')
    MEMBER_UPDATED = 'member.updated', _('Member updated')
    MEMBER_ROLE_CHANGED = 'member.role_changed', _('Member role changed')
    MEMBER_REMOVED = 'member.removed', _('Member removed')
    INVITATION_CREATED = 'invitation.created', _('Invitation created')
    INVITATION_UPDATED = 'invitation.updated', _('Invitation updated')
    INVITATION_EMAIL_SENT = 'invitation.email_sent', _('Invitation email sent')
    INVITATION_DELETED = 'invitation.deleted', _('Invitation deleted')
    INVITATION_ACCEPTED = 'invitation.accepted', _('Invitation accepted')
    INVITATION_DECLINED = 'invitation.declined', _('Invitation declined')
    TEAM_CREATED = 'team.created', _('Team created')
    TEAM_UPDATED = 'team.updated', _('Team updated')
    TEAM_DELETED = 'team.deleted', _('Team deleted')
    TEAM_MEMBER_ADDED = 'team_member.added', _('Team member added')
    TEAM_MEMBER_UPDATED = 'team_member.updated', _('Team member updated')
    TEAM_MEMBER_REMOVED = 'team_member.removed', _('Team member removed')
    STORED_FILE_UPLOADED = 'stored_file.uploaded', _('File uploaded')
    STORED_FILE_UPDATED = 'stored_file.updated', _('File updated')
    STORED_FILE_DELETED = 'stored_file.deleted', _('File deleted')
    AUTH_SIGNUP = 'auth.signup', _('Account created')
    AUTH_LOGIN_SUCCEEDED = 'auth.login.succeeded', _('Signed in')
    AUTH_LOGIN_FAILED = 'auth.login.failed', _('Failed sign-in attempt')
    AUTH_LOGOUT = 'auth.logout', _('Signed out')
    AUTH_PASSWORD_CHANGED = (
        'auth.password.changed',
        _('Password changed'),
    )
    AUTH_PASSWORD_CHANGE_FAILED = (
        'auth.password_change.failed',
        _('Failed password change attempt'),
    )
    AUTH_PASSWORD_RESET_REQUESTED = (
        'auth.password_reset.requested',
        _('Password reset requested'),
    )
    AUTH_PASSWORD_RESET_COMPLETED = (
        'auth.password_reset.completed',
        _('Password reset completed'),
    )
    AUTH_PASSWORD_RESET_FAILED = (
        'auth.password_reset.failed',
        _('Failed password reset attempt'),
    )
    AUTH_EMAIL_VERIFIED = 'auth.email.verified', _('Email verified')
    AUTH_EMAIL_VERIFICATION_FAILED = (
        'auth.email_verification.failed',
        _('Failed email verification attempt'),
    )
    USER_PROFILE_UPDATED = 'user.profile.updated', _('Profile updated')


class AuditActorTypeChoices(models.TextChoices):
    USER = 'user', _('User')
    PLATFORM = 'platform', _('Platform')
    SYSTEM = 'system', _('System')


ACCOUNT_ACTION_PREFIXES = ('auth.', 'user.')
