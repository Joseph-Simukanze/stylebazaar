# products/forms.py

from django import forms
from django.forms import inlineformset_factory
from .models import Product, Category, ProductImage, Promotion


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "category",
            "name",
            "description",
            "price",
            "discounted_price",
            "stock",
            "is_promoted",
        ]
        widgets = {
            "description": forms.Textarea(attrs={
                "rows": 5,
                "placeholder": "Describe your product in detail...",
            }),
            "price": forms.NumberInput(attrs={
                "step": "0.01",
                "min": "0",
                "placeholder": "0.00",
            }),
            "discounted_price": forms.NumberInput(attrs={
                "step": "0.01",
                "min": "0",
                "placeholder": "Leave blank for no discount",
            }),
            "stock": forms.NumberInput(attrs={
                "min": "0",
                "placeholder": "e.g., 100",
            }),
            "is_promoted": forms.CheckboxInput(),
        }
        labels = {
            "category": "Product Category",
            "name": "Product Name",
            "description": "Description",
            "price": "Original Price (K)",
            "discounted_price": "Discounted Price (K)",
            "stock": "Stock Quantity",
            "is_promoted": "Feature this product on homepage",
        }
        help_texts = {
            "discounted_price": "Optional. Must be lower than original price.",
            "is_promoted": "Promoted products appear in featured sections.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Fix: use is_approved instead of is_active
        self.fields["category"].queryset = Category.objects.filter(is_approved=True)

        if not self.fields["category"].queryset.exists():
            self.fields["category"].disabled = True
            self.fields["category"].help_text = (
                "No approved categories available. Please contact the administrator."
            )

        # Optional: Add Tailwind-friendly classes
        # (You can remove this if you prefer to style via widget_tweaks in the template)
        for field_name, field in self.fields.items():
            if field_name != "is_promoted":
                field.widget.attrs.update({
                    "class": (
                        "w-full px-5 py-3 rounded-xl border border-gray-300 dark:border-gray-600 "
                        "bg-white dark:bg-gray-700 text-gray-900 dark:text-white "
                        "focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-pink-500 "
                        "transition"
                    )
                })

    def clean(self):
        cleaned_data = super().clean()
        price = cleaned_data.get("price")
        discounted_price = cleaned_data.get("discounted_price")

        if discounted_price and price and discounted_price >= price:
            raise forms.ValidationError(
                "Discounted price must be less than the original price."
            )

        return cleaned_data


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "slug", "image"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g., Women's Fashion"}),
            "slug": forms.TextInput(attrs={"placeholder": "Auto-generated from name"}),
            "image": forms.FileInput(),
        }
        help_texts = {
            "slug": "Leave blank to auto-generate from name.",
            "image": "Optional banner image for the category page.",
        }


# Custom formset that enforces at least 3 images
class RequiredProductImageFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        # Skip validation if there are already errors
        if any(self.errors):
            return

        # Count non-deleted, non-empty images
        uploaded_count = sum(
            1
            for form in self.forms
            if form.cleaned_data
            and not form.cleaned_data.get("DELETE", False)
            and form.cleaned_data.get("image")
        )

        if uploaded_count < 3:
            raise forms.ValidationError(
                "You must upload at least 3 high-quality images for your product."
            )


# Product Images FormSet
ProductImageFormSet = inlineformset_factory(
    Product,
    ProductImage,
    formset=RequiredProductImageFormSet,
    fields=("image",),
    extra=5,                    # Show 5 upload slots
    min_num=3,                  # Require at least 3
    max_num=10,                 # Optional upper limit
    validate_min=True,
    can_delete=True,            # Allow removing images when editing
    widgets={
        "image": forms.FileInput(attrs={
            "accept": "image/*",
            # "class": "hidden"   # usually hidden by CSS in template
        })
    }
)


class PromotionForm(forms.ModelForm):
    class Meta:
        model = Promotion
        fields = ["title", "discount_type", "discount_value", "start_date", "end_date"]
        widgets = {
            "title": forms.TextInput(attrs={
                "placeholder": "e.g., New Year Flash Sale – Up to 50% Off"
            }),
            "discount_type": forms.Select(),
            "discount_value": forms.NumberInput(attrs={
                "min": "0",
                "step": "0.01",
                "placeholder": "e.g., 30 for 30%"
            }),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "title": "Promotion Title",
            "discount_type": "Discount Type",
            "discount_value": "Discount Amount",
            "start_date": "Start Date",
            "end_date": "End Date",
        }
        help_texts = {
            "discount_value": "Enter percentage (e.g., 25) or fixed amount depending on type.",
            "end_date": "Leave blank for ongoing promotion.",
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError("End date cannot be earlier than start date.")

        return cleaned_data