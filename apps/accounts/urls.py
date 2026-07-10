from django.conf import settings
from django.urls import include, path
from rest_framework import routers
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from apps.accounts.views import auth
from apps.accounts.views.files import StoredFileViewSet
from apps.accounts.views.invitations import InvitationViewSet
from apps.accounts.views.members import MemberViewSet
from apps.accounts.views.organization_images import OrganizationImageViewSet
from apps.accounts.views.organization_profiles import OrganizationProfileViewSet
from apps.accounts.views.organizations import OrganizationViewSet
from apps.accounts.views.session import SessionView
from apps.accounts.views.session_config import session_config
from apps.accounts.views.signup import SignupViewSet

app_name = 'accounts'


router = routers.DefaultRouter()
router.register(r'signup', SignupViewSet, basename='signup')
router.register(r'organizations', OrganizationViewSet, basename='organizations')
router.register(r'members', MemberViewSet, basename='members')
router.register(r'invitations', InvitationViewSet, basename='invitations')
router.register(r'stored-files', StoredFileViewSet, basename='stored_files')
router.register(
    r'organization-images', OrganizationImageViewSet, basename='organization_images'
)
router.register(
    r'organization-profiles',
    OrganizationProfileViewSet,
    basename='organization_profiles',
)


authentication_urlpatterns = [
    # Authentication (JWT)
    path(
        'api/auth/token/', auth.TokenObtainPairView.as_view(), name='token_obtain_pair'
    ),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    # Logout
    path('api/auth/logout/', auth.LogoutView.as_view(), name='logout'),
    # Password reset
    path(
        'api/auth/password/reset/',
        auth.PasswordResetRequestView.as_view(),
        name='password_reset',
    ),
    path(
        'api/auth/password/reset/confirm/',
        auth.PasswordResetConfirmView.as_view(),
        name='password_reset_confirm',
    ),
]

accounts_urlpatterns = [
    path('api/accounts/', include(router.urls)),
    path('api/accounts/session/', SessionView.as_view(), name='session'),
    path(
        'api/accounts/session/config/',
        session_config,
        name='session-config',
    ),
]

urlpatterns = authentication_urlpatterns + accounts_urlpatterns

if settings.ENVIRONMENT in ['local_development', 'test']:
    from apps.accounts.emails import InvitationEmail, PasswordResetRequestEmail

    urlpatterns += [
        path(
            route='email-preview/auth/password/reset/',
            view=PasswordResetRequestEmail.as_view(),
            name='password_reset_email_preview',
        ),
        path(
            route='email-preview/accounts/invitation/',
            view=InvitationEmail.as_view(),
            name='invitation_email_preview',
        ),
    ]
