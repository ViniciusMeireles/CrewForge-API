# Review Checklist

## Architecture
- [ ] MRO order correct: OrganizationScopedViewSetMixin → ModelViewSetMixin → viewsets.ModelViewSet
- [ ] Imports from generics (apps/generics/), not apps/accounts/
- [ ] @extend_schema_model_view_set decorator present
- [ ] label_expression or value_expression on ViewSet
- [ ] Barrel exports in __init__.py

## Permissions
- [ ] super().has_object_permission() called
- [ ] get_member(request) used for member lookup
- [ ] Role checks use has_{role}_permission properties
- [ ] organization_lookup defined correctly
- [ ] No hardcoded role strings

## Tests
- [ ] 19-scenario coverage matrix covered
- [ ] Factory used (no hardcoded IDs)
- [ ] self.new_account() setup present in setUp
- [ ] Cross-org tests included (read filtered, write 403/404)
- [ ] Soft-delete verified (is_active=False after delete)
- [ ] 404 test for nonexistent object

## Naming
- [ ] verbose_name on model fields
- [ ] help_text on serializer fields
- [ ] related_name on ForeignKey fields
- [ ] __str__ method on model
- [ ] Meta class with verbose_name

## Code Quality
- [ ] No unused imports
- [ ] Consistent code style
- [ ] Proper error handling
- [ ] No security issues (secrets, hardcoded values)

## Documentation
- [ ] Docstrings on classes and methods
- [ ] Comments for complex logic
- [ ] README updated (if needed)
