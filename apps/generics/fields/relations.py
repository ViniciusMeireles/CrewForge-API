class PrimaryKeyActiveRelatedFieldMixin:
    """
    Mixin to filter queryset based on the is_active field.
    """

    def get_queryset(self):
        """
        Override the get_queryset method to filter queryset based on the is_active
        field.
        This is useful for models that have an is_active field to filter out inactive
        records.
        """
        queryset = super().get_queryset()
        model = queryset.model
        filters = {'is_active': True} if hasattr(model, 'is_active') else {}
        return queryset.filter(**filters)
