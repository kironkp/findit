from django import forms
from django.core.files.base import ContentFile

from .icons import ICON_SLUGS, suggest_icon
from .models import Item, Location, LocationLog
from .services.image_search import fetch_first_image


class ItemForm(forms.ModelForm):
    new_location = forms.CharField(
        required=False,
        max_length=100,
        label='Or add a new location',
        help_text='Type a name to create a new location and use it for this item.',
    )

    field_order = [
        'name',
        'description',
        'distinguishing_detail',
        'quantity',
        'photo',
        'location',
        'new_location',
        'tags',
    ]

    class Meta:
        model = Item
        fields = [
            'name',
            'description',
            'distinguishing_detail',
            'quantity',
            'photo',
            'location',
            'tags',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'tags': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user
        if user is not None:
            self.fields['location'].queryset = Location.objects.filter(user=user)
        self.fields['location'].empty_label = '— No location yet —'

    def clean(self):
        cleaned = super().clean()
        new_name = (cleaned.get('new_location') or '').strip()
        if new_name and cleaned.get('location'):
            raise forms.ValidationError(
                'Pick an existing location or type a new one — not both.'
            )
        cleaned['new_location'] = new_name
        return cleaned

    def save(self, commit=True):
        new_name = self.cleaned_data.get('new_location', '')
        if new_name and self._user is not None:
            location, _ = Location.objects.get_or_create(
                user=self._user, name=new_name
            )
            self.instance.location = location

        if not self.instance.photo:
            query = self.instance.name
            if self.instance.distinguishing_detail:
                query = f'{query} {self.instance.distinguishing_detail}'
            result = fetch_first_image(query)
            if result:
                filename, data = result
                self.instance.photo.save(filename, ContentFile(data), save=False)

        return super().save(commit=commit)


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ['name', 'parent', 'is_person', 'icon', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
            'icon': forms.HiddenInput(),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            qs = Location.objects.filter(user=user)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            self.fields['parent'].queryset = qs
        self.fields['parent'].empty_label = '— Top-level location —'

    def clean_icon(self):
        icon = (self.cleaned_data.get('icon') or '').strip()
        if icon and icon not in ICON_SLUGS:
            return ''
        return icon

    def save(self, commit=True):
        if not self.instance.icon:
            self.instance.icon = suggest_icon(self.instance.name) or ''
        return super().save(commit=commit)


class MoveForm(forms.ModelForm):
    new_location = forms.CharField(
        required=False,
        max_length=100,
        label='Or create a new location',
        help_text='Type a name to create a new location and move the item there.',
    )

    field_order = ['location', 'new_location', 'note', 'return_by']

    class Meta:
        model = LocationLog
        fields = ['location', 'note', 'return_by']
        widgets = {
            'return_by': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date'},
            ),
            'note': forms.TextInput(attrs={'placeholder': 'Optional note (e.g. "lent to brother")'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user
        if user is not None:
            self.fields['location'].queryset = Location.objects.filter(user=user)
        self.fields['location'].empty_label = '— Choose a location —'
        self.fields['location'].label = 'New item location'

    def clean(self):
        cleaned = super().clean()
        new_name = (cleaned.get('new_location') or '').strip()
        if new_name and cleaned.get('location'):
            raise forms.ValidationError(
                'Pick an existing location or create a new one — not both.'
            )
        if not new_name and not cleaned.get('location'):
            raise forms.ValidationError(
                'Choose a location or type a new one to move the item.'
            )
        cleaned['new_location'] = new_name
        return cleaned

    def save(self, commit=True):
        new_name = self.cleaned_data.get('new_location', '')
        if new_name and self._user is not None:
            location, _ = Location.objects.get_or_create(
                user=self._user, name=new_name
            )
            self.instance.location = location
        return super().save(commit=commit)
