from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

User = get_user_model()


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    role = forms.ChoiceField(
        choices=User.ROLE_CHOICES,
        widget=forms.RadioSelect,
        required=True,
        label="Register as"
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "phone_number",
            "role",
            "password1",
            "password2",
        )

    def save(self, commit=True):
        """
        Ensure email + role are saved correctly.
        Profiles are created via post_save signal.
        """
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.role = self.cleaned_data["role"]

        if commit:
            user.save()

        return user
from .models import Profile

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("avatar", "phone", "address")
# users/forms.py

from django import forms
from .models import Address

class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = [
            'full_name', 'phone', 'address_line_1', 'address_line_2',
            'city', 'state', 'postal_code', 'country', 'is_default'
        ]
        widgets = {
            'address_line_2': forms.TextInput(attrs={'placeholder': 'Apartment, suite, etc. (optional)'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'w-5 h-5 text-pink-600 rounded focus:ring-pink-500'}),
        }
        labels = {
            'is_default': 'Make this my default address',
        }