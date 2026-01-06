# orders/forms.py

from django import forms
from .models import DeliveryOption


class CheckoutForm(forms.Form):
    """
    Checkout form for collecting shipping information and delivery option.
    Does NOT use ModelForm because Order is created later in the view.
    """

    full_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'placeholder': 'John Doe',
            'autocomplete': 'name',
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'john@example.com',
            'autocomplete': 'email',
        })
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '+260 97 1234567',
            'autocomplete': 'tel',
        })
    )
    address = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'House number, street, area, city, province...',
            'autocomplete': 'street-address',
            'class': 'resize-none',
        })
    )
    delivery_option = forms.ModelChoiceField(
        queryset=DeliveryOption.objects.none(),  # Will be populated in __init__
        widget=forms.RadioSelect,
        empty_label=None,
        required=True,
    )

    class Meta:
        labels = {
            'full_name': 'Full Name',
            'email': 'Email Address',
            'phone': 'Phone Number',
            'address': 'Delivery Address',
            'delivery_option': 'Delivery Option',
        }
        help_texts = {
            'address': 'Include house number, street, area, city, and province for accurate delivery.',
            'phone': 'Optional, but recommended for delivery updates.',
        }

    def __init__(self, *args, **kwargs):
        # Allow passing delivery options from the view
        delivery_options = kwargs.pop('delivery_options', None)
        super().__init__(*args, **kwargs)

        # Make phone optional
        self.fields['phone'].required = False

        # Load active delivery options
        if delivery_options is None:
            delivery_options = DeliveryOption.objects.filter(is_active=True).order_by('price')

        self.fields['delivery_option'].queryset = delivery_options
        self.fields['delivery_option'].empty_label = None

        # Attach price as data-cost for JavaScript total calculation
        for option in delivery_options:
            # Add data-cost attribute to each radio button
            self.fields['delivery_option'].widget.attrs.update({
                'data-cost': str(float(option.price))
            })

        # Optional: Customize choice label to include price and estimated days
        choices = []
        for option in delivery_options:
            label = f"{option.name} — K{option.price} ZMW"
            if option.estimated_days:
                label += f" ({option.estimated_days} days)"
            choices.append((option.pk, label))

        self.fields['delivery_option'].choices = choices

    def clean_delivery_option(self):
        delivery_option = self.cleaned_data.get('delivery_option')
        if delivery_option and not delivery_option.active:  # ← change here too
            raise forms.ValidationError("This delivery option is no longer available.")
        return delivery_option

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            # Basic cleaning: remove spaces, dashes, etc.
            phone = ''.join(filter(str.isdigit, phone))
            if phone.startswith('260') and len(phone) != 12:
                raise forms.ValidationError("Invalid Zambian phone number format.")
            if phone.startswith('0') and len(phone) != 10:
                raise forms.ValidationError("Local numbers should be 10 digits (e.g., 0971234567).")
        return phone