from apps.accounts.factories.users import UserFactory


class PlatformTestMixin:
    def authenticate_staff(self, role: str = 'support'):
        user = UserFactory(platform_role=role)
        self.client.force_authenticate(user=user)
        return user
