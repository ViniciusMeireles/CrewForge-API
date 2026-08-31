# TDD Cycle Reference

## Red-Green-Refactor

### Red Phase
- Write minimal test
- Run `make l_test_fast`
- Confirm failure
- Show failing test

### Green Phase
- Write minimum code
- Run `make l_test_fast`
- Confirm passing
- Show implementation

### Refactor Phase
- Improve structure
- Run `make l_test_fast`
- Confirm still passing
- Show refactored code

## Commands

```bash
# Fast test (no coverage)
make l_test_fast

# Full test (with coverage)
make l_test

# Format code
make l_format_code
```

## Test Structure

```python
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.tests.mixins import APITestCaseMixin


class FeatureTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse("app:resource-list")

    def test_feature_behavior(self):
        """Test expected behavior."""
        # Arrange
        # Act
        # Assert
```

## Best Practices

1. One test per cycle
2. Minimal assertions
3. Clear test names
4. Arrange-Act-Assert pattern
5. Use factories, not hardcoded data
