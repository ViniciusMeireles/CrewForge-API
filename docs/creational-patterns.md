# Creational Design Patterns

This document describes the creational design patterns used in CrewForge.

---

## Table of Contents

- [Factory Method Pattern](#factory-method-pattern)
- [Builder Pattern](#builder-pattern)

---

## Factory Method Pattern

CrewForge uses [factory_boy](https://factoryboy.readthedocs.io/) with a custom mixin to provide consistent test data generation.

### ModelFactoryMixin

Location: `apps/generics/factories/mixins.py`

Base mixin applied to all factories, ensuring every model instance has `is_active = True` and a generated `id`.

```python
class ModelFactoryMixin:
    id = factory.Faker('id')
    is_active = True
```

### Factory Convention

All factories follow these rules:

1. Extend both `ModelFactoryMixin` and `DjangoModelFactory`
2. Use `factory.SubFactory` for ForeignKey relationships
3. Use `factory.LazyAttribute` for derived fields (e.g., `slug` from `name`)
4. Use `factory.post_generation` for related object creation when needed
5. Use `factory.SelfAttribute` to propagate shared context across `SubFactory`
   chains (e.g., ensuring team and member belong to the same organization)
6. Use `factory.Trait` via inner `Params` class for named scenario variations
   (e.g., file type, permission level)
7. Use `factory.Sequence` for unique field generation (e.g., email, username)
8. Use `factory.django.FileField` for file-based fields
9. Use `skip_postgeneration_save = True` as an optimization to avoid redundant
   saves after post-generation hooks

> **Note**: `UserFactory` is an exception — it extends `DjangoModelFactory`
> directly (not `ModelFactoryMixin`) because `User` inherits from
> `AbstractUser` which already provides `id` via `AutoField`. It defines
> `is_active` directly as a class attribute.

### OrganizationFactory

Location: `apps/accounts/factories/organizations.py`

```python
class OrganizationFactory(ModelFactoryMixin, DjangoModelFactory):
    name = factory.Faker('company')
    slug = factory.LazyAttribute(lambda o: slugify(o.name))

    class Meta:
        model = Organization
        skip_postgeneration_save = True

    @factory.post_generation
    def owner(self, create, extracted, **kwargs):
        if not create:
            return
        from apps.accounts.factories.members import MemberFactory
        from apps.accounts.factories.users import UserFactory
        owner_user = UserFactory()
        self.owner = MemberFactory(
            user=owner_user, organization=self, role=MemberRoleChoices.OWNER.value
        )
        self.save()

```

### OrganizationProfileFactory

Location: `apps/accounts/factories/organizations.py` (same file)

```python
class OrganizationProfileFactory(ModelFactoryMixin, DjangoModelFactory):
    organization = factory.SubFactory(OrganizationFactory)
    website = factory.Faker('url')
    description = factory.Faker('text')

    class Meta:
        model = OrganizationProfile
```

### MemberFactory

Location: `apps/accounts/factories/members.py`

```python
class MemberFactory(ModelFactoryMixin, DjangoModelFactory):
    nickname = factory.Faker('user_name')
    user = factory.SubFactory(UserFactory)
    organization = factory.SubFactory(
        factory='apps.accounts.factories.organizations.OrganizationFactory',
    )
    role = MemberRoleChoices.MEMBER

    class Meta:
        model = Member
```

### TeamFactory

Location: `apps/teams/factories/teams.py`

```python
class TeamFactory(ModelFactoryMixin, DjangoModelFactory):
    name = factory.Faker('company')
    slug = factory.LazyAttribute(lambda o: slugify(o.name))
    description = factory.Faker('text', max_nb_chars=200)
    organization = factory.SubFactory(
        factory='apps.accounts.factories.organizations.OrganizationFactory',
    )

    class Meta:
        model = Team
```

### Additional Factories

#### UserFactory

Location: `apps/accounts/factories/users.py`

Extends `DjangoModelFactory` directly (not `ModelFactoryMixin` — see convention
note above). Uses `factory.Sequence` for unique emails and `post_generation`
for password hashing.

```python
class UserFactory(DjangoModelFactory):
    username = factory.Faker('user_name')
    email = factory.Sequence(lambda n: f'unit_test_user{n}@example.com')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True

    class Meta:
        model = User
        skip_postgeneration_save = True

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        self.password = 'passWord*123'
        if create:
            self.set_password('passWord*123')
            self.save()
```

#### StoredFileFactory

Location: `apps/accounts/factories/files.py`

Heavily uses `factory.Trait` via inner `Params` class for both permission levels
and file type variations:

```python
class StoredFileFactory(ModelFactoryMixin, DjangoModelFactory):
    file = factory.django.FileField(filename='test.txt', data=b'Hello, World!')
    viewing_permission = StoredFileAccess.OWNER
    updating_permission = StoredFileAccess.OWNER
    owner = factory.SubFactory('apps.accounts.factories.users.UserFactory')
    organization = factory.SubFactory(
        'apps.accounts.factories.organizations.OrganizationFactory',
    )

    class Meta:
        model = StoredFile

    class Params:
        # Permission traits
        public = factory.Trait(viewing_permission=StoredFileAccess.PUBLIC, ...)
        org_members = factory.Trait(...)
        org_managers = factory.Trait(...)
        org_admins = factory.Trait(...)
        org_owners = factory.Trait(...)

        # File type traits (pdf, png, jpg, gif, webp, svg, csv, html, json, xml, zip, gz, ...)
        pdf = factory.Trait(
            file=factory.django.FileField(filename='test.pdf', data=b'%PDF-1.4...'),
        )
```

Usage:

```python
StoredFileFactory(pdf=True, public=True)
StoredFileFactory(txt=True, org_admins=True)
```

#### InvitationFactory

Location: `apps/accounts/factories/invitations.py`

```python
class InvitationFactory(ModelFactoryMixin, DjangoModelFactory):
    email = factory.Sequence(lambda n: f'unit_test_invite{n}@example.com')
    is_accepted = False
    is_expired = False
    expired_at = factory.Faker('date_time', tzinfo=timezone.utc)
    role = MemberRoleChoices.MEMBER
    organization = factory.SubFactory(
        factory='apps.accounts.factories.organizations.OrganizationFactory',
    )

    class Meta:
        model = Invitation
        skip_postgeneration_save = True
```

#### OrganizationImageFactory

Location: `apps/accounts/factories/organization_image.py`

Uses `SelfAttribute` to propagate organization context from profile to the
nested `StoredFile`:

```python
class OrganizationImageFactory(ModelFactoryMixin, DjangoModelFactory):
    profile = factory.SubFactory(
        'apps.accounts.factories.organizations.OrganizationProfileFactory',
    )
    image_type = OrganizationImageTypeChoices.LOGO
    image = factory.SubFactory(
        StoredFileFactory,
        organization=factory.SelfAttribute('..profile.organization'),
        public=True,
    )

    class Meta:
        model = OrganizationImage
```

#### TeamMemberFactory

Location: `apps/teams/factories/team_members.py`

Uses `SelfAttribute` with `..` traversal to ensure team and member belong to
the same organization:

```python
class TeamMemberFactory(ModelFactoryMixin, DjangoModelFactory):
    team = factory.SubFactory(
        'apps.teams.factories.teams.TeamFactory',
        organization=factory.SelfAttribute('..organization'),
    )
    member = factory.SubFactory(
        'apps.accounts.factories.members.MemberFactory',
        organization=factory.SelfAttribute('..organization'),
    )
    role = TeamMemberRoleChoices.MEMBER

    class Meta:
        model = TeamMember

    class Params:
        organization = factory.SubFactory(
            'apps.accounts.factories.organizations.OrganizationFactory'
        )
```

### Factory Usage in Tests

```python
# Create with DB persistence
org = OrganizationFactory.create()
member = MemberFactory.create(organization=org)

# Build without DB persistence
team = TeamFactory.build()

# Batch creation
members = MemberFactory.create_batch(5, organization=org)

# Trait usage
file = StoredFileFactory(pdf=True, public=True)
image = OrganizationImageFactory(image_type=OrganizationImageTypeChoices.COVER)

# Context propagation
team_member = TeamMemberFactory()
assert team_member.team.organization == team_member.member.organization  # True
```

---

## Builder Pattern

The Builder pattern constructs complex objects step by step. CrewForge uses this for email composition.

### EmailBase as Builder

Location: `apps/generics/mails/bases.py`

`EmailBase` acts as a builder for `EmailMultiAlternatives` messages. Configuration happens through attributes and constructor kwargs, then `get_message()` builds the final object.

```python
# Step 1: Configure via subclass attributes
class PasswordResetRequestEmail(EmailBase):
    template_name = 'accounts/emails/base.html'
    subject = _('Password Reset')
    preheader = _('Use the link below to reset your password.')
    title = _('Password Reset Request')
    content = _('Click the button below to set a new password.')

    def __init__(self, *, reset_url: str, **kwargs):
        super().__init__(**kwargs)
        self.cta = CTAEmail(url=reset_url, text=_('Reset Password'))

# Step 2: Build with constructor kwargs
email = PasswordResetRequestEmail(
    recipient_list=['user@example.com'],
    reset_url='https://app.example.com/reset?token=abc123',
)

# Step 3: Get the built message
message = email.get_message()

# Step 4: Send
email.send()
```

### CTAEmail

Location: `apps/generics/mails/bases.py`

Helper builder for Call-To-Action buttons within emails:

```python
class CTAEmail:
    def __init__(
        self,
        *,
        url: str,
        text: str = _('Click Here'),
        color: str = '#002180',
        text_color: str = '#FFFFFF',
    ):
        self.url = url
        self.text = text
        self.color = color
        self.text_color = text_color
```

**Usage:**

```python
self.cta = CTAEmail(
    url=reset_url,
    text=_('Reset Password'),
    color='#FF5733',
)
```

### EmailView for Preview

`EmailView` provides a Django view that builds the email in preview mode for development:

```python
# Only available in local/test environments
if settings.ENVIRONMENT in ['local_development', 'test']:
    urlpatterns += [
        path(
            route='email-preview/auth/password/reset/',
            view=PasswordResetRequestEmail.as_view(),
            name='password_reset_email_preview',
        )
    ]
```

---

## Related Patterns

- [Structural Patterns](./structural-patterns.md) (Mixin, Abstract Model, Module)
- [Behavioral Patterns](./behavioral-patterns.md) (Template Method, Strategy, Validation)
- [Architectural Patterns](./architectural-patterns.md) (Layered, Facade, Test Infrastructure)
- [Test Patterns](./test-patterns.md) (Modular test structure, coverage matrix)
