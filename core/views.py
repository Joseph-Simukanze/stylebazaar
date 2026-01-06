from django.shortcuts import render
from products.models import Category, Product  # Add Product import

def home(request):
    categories = Category.objects.all()
    
    # Get the latest 12 products (or adjust the number as needed)
    # Assuming your Product model has a 'created_at' DateTimeField
    # Common field names: created_at, date_added, created, etc.
    recent_products = Product.objects.order_by('-created_at')[:12]
    
    # If your model uses a different field name for creation date, change it accordingly
    # e.g., '-date_added' or '-pub_date'
    
    return render(request, "core/home.html", {
        "categories": categories,
        "recent_products": recent_products,
    })