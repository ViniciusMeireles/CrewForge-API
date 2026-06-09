from django import forms

from apps.accounts.models.files import StoredFile
from apps.accounts.serializers.files import StoredFileCreateUpdateModelSerializer


class StoredFileModelForm(forms.ModelForm):
    class Meta:
        model = StoredFile
        fields = [
            'file',
            'name',
            'viewing_permission',
            'updating_permission',
            'owner',
            'organization',
            'size',
            'content_type',
            'original_name',
        ]

    def __init__(self, *args, **kwargs):
        super(StoredFileModelForm, self).__init__(*args, **kwargs)
        readonly_fields = [
            'original_name',
            'content_type',
            'size',
        ]
        for field_name in readonly_fields:
            self.fields[field_name].widget.attrs['disabled'] = True
            self.fields[field_name].required = False

    def clean(self):
        super(StoredFileModelForm, self).clean()

        data = self.data.copy()
        if not data.get('file') and self.files:
            data.update(self.files)
        serializer = StoredFileCreateUpdateModelSerializer(
            instance=self.instance,
            data=data,
        )
        is_valid = serializer.is_valid()
        self.cleaned_data.update(serializer.validated_data)
        if not is_valid:
            for field, errors in serializer.errors.items():
                for error in errors:
                    error = error.replace("{'", '').replace("'}", '')
                    self.add_error(field=field, error=error)
        return self.cleaned_data
