from django.db.models import Sum

from apps.accounts.models.files import StoredFile
from apps.accounts.models.invitation import Invitation
from apps.accounts.models.member import Member
from apps.accounts.models.organization import Organization
from apps.billing.entitlements import (
    MAX_MEMBERS,
    MAX_TEAMS,
    plan_for,
    storage_bytes,
    value,
)
from apps.billing.models.subscription import Subscription
from apps.teams.models.team import Team


def active_members_count(organization: Organization) -> int:
    return Member.objects.filter(organization=organization, is_active=True).count()


def pending_invitations_count(organization: Organization) -> int:
    return Invitation.objects.filter(organization=organization).filter_pending().count()


def active_teams_count(organization: Organization) -> int:
    return Team.objects.filter(organization=organization, is_active=True).count()


def used_storage_bytes(organization: Organization) -> int:
    total = StoredFile.objects.filter(
        organization=organization, is_active=True
    ).aggregate(total=Sum('size'))['total']
    return total or 0


def usage(organization: Organization) -> dict[str, dict[str, int | None]]:
    plan = plan_for(organization)
    return {
        'members': {
            'current': active_members_count(organization),
            'max': value(plan, MAX_MEMBERS),
        },
        'teams': {
            'current': active_teams_count(organization),
            'max': value(plan, MAX_TEAMS),
        },
        'storage': {
            'current': used_storage_bytes(organization),
            'max': storage_bytes(plan),
        },
    }


def session_subscription(member: Member | None) -> Subscription | None:
    if member is None or not member.has_billing_access:
        return None
    try:
        return member.organization.subscription
    except Subscription.DoesNotExist:
        return None


def _plan_summary(plan) -> dict:
    return {'code': plan.code, 'name': plan.name}


def subscription_detail(subscription: Subscription, *, can_manage: bool) -> dict:
    from apps.billing import pricing
    from apps.billing.models.billing_profile import BillingProfile
    from apps.billing.models.invoice import Invoice

    organization = subscription.organization
    next_charge = None
    if subscription.is_paid and not subscription.cancel_at_period_end:
        plan = subscription.scheduled_plan or subscription.plan
        cycle = subscription.scheduled_cycle or subscription.paid_cycle()
        next_charge = {
            'amount': pricing.price(plan, cycle),
            'date': subscription.paid_period_end().date(),
        }
    scheduled_change = None
    if subscription.scheduled_plan_id is not None:
        scheduled_change = {
            'plan': _plan_summary(subscription.scheduled_plan),
            'cycle': subscription.scheduled_cycle,
            'effective_at': subscription.current_period_end,
        }
    pending_change = None
    if subscription.pending_plan_id is not None:
        invoice = (
            Invoice.objects.open()
            .filter(subscription=subscription, plan_id=subscription.pending_plan_id)
            .order_by('-issued_at')
            .first()
        )
        pending_change = {
            'plan': _plan_summary(subscription.pending_plan),
            'cycle': subscription.pending_cycle,
            'amount': invoice.amount if invoice else None,
            'invoice': invoice.pk if invoice else None,
            'payment_url': invoice.payment_url
            if invoice and can_manage and invoice.payment_url
            else None,
        }
    profile = BillingProfile.objects.filter(organization=organization).first()
    return {
        'plan': subscription.plan,
        'status': subscription.status,
        'cycle': subscription.cycle,
        'trial_ends_at': subscription.trial_ends_at,
        'is_complimentary': subscription.is_complimentary,
        'usage': usage(organization),
        'current_period_end': subscription.current_period_end,
        'next_charge': next_charge,
        'cancel_at_period_end': subscription.cancel_at_period_end,
        'scheduled_change': scheduled_change,
        'pending_change': pending_change,
        'billing_profile_complete': bool(profile and profile.is_complete),
    }
