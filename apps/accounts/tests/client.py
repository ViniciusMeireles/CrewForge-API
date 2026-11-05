from rest_framework.test import APIClient

from apps.accounts.factories.members import MemberFactory
from apps.accounts.models.member import Member


class CustomAPIClient(APIClient):
    def force_authenticate(
        self,
        user=None,
        token=None,
        member: MemberFactory | Member | None = None,
        organization_auth: bool = True,
    ):
        """Force authentication of the user, token, or member."""
        if not member:
            super().force_authenticate(user=user, token=token)
            return

        super().force_authenticate(user=member.user, token=token)
        if organization_auth:
            session = self.session
            session['organization_id'] = member.organization_id
            session.save()
