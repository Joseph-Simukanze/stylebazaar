from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db.models import Sum, F
from datetime import timedelta
from django.db.models import Sum, F, FloatField
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from products.models import Product
from orders.models import Order, OrderItem
from users.decorators import seller_required
from .models import Product, Category, Promotion
from .forms import (
    ProductForm,
    ProductImageFormSet,
    CategoryForm,
    PromotionForm,
)
# from orders.models import OrderItem  # Uncomment if you have this app


# =======================
# PUBLIC VIEWS
# =======================

from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from .models import Product, Category

# (Duplicate imports kept as-is — harmless but can be cleaned later)

from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from .models import Product, Category

from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from products.models import Product, Category


def product_list(request):
    category_slug = request.GET.get("category")
    query = request.GET.get("q")

    # Base queryset: only visible products for buyers
    products = Product.objects.filter(
        is_active=True,
        is_approved=True
    ).select_related(
        "category",
        "seller"
    ).prefetch_related(
        "images"
    ).order_by("-created_at")

    selected_category = None

    # Filter by category
    if category_slug:
        selected_category = get_object_or_404(Category, slug=category_slug, is_approved=True)
        products = products.filter(category=selected_category)

    # Search in name or description
    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )

    # Categories for sidebar (only approved ones)
    categories = Category.objects.filter(is_approved=True).order_by("name")

    context = {
        "products": products,
        "categories": categories,
        "selected_category": selected_category,
        "search_query": query,
    }

    return render(request, "products/product_list.html", context)


from django.shortcuts import render, get_object_or_404
from django.db.models import Prefetch
from .models import Category, Product, ProductImage  # Adjust if ProductImage is in a different app


def category_detail(request, slug):
    """
    Display all approved and active products in a specific category.
    Only shows approved categories to buyers.
    """
    category = get_object_or_404(
        Category,
        slug=slug,
        is_approved=True
    )

    products = (
        Product.objects.filter(
            category=category,
            is_active=True,
            is_approved=True
        )
        .select_related("seller")
        .prefetch_related("images")  # Loads all images efficiently
        .order_by("-created_at")
    )

    categories = Category.objects.filter(is_approved=True).order_by("name")

    context = {
        "category": category,
        "products": products,
        "categories": categories,
        "page_title": f"{category.name} - Style Bazaar",
    }

    return render(request, "products/category_detail.html", context)


@require_http_methods(["GET", "HEAD"])
def product_detail(request, slug):
    """Now uses slug instead of pk for SEO-friendly URLs"""
    product = get_object_or_404(
        Product.objects
        .select_related("category", "seller")
        .prefetch_related("images")
        .filter(is_active=True, is_approved=True),
        slug=slug
    )
    return render(request, "products/product_detail.html", {"product": product})


# =======================
# CATEGORY LIST (PUBLIC + STAFF MANAGEMENT)
# =======================

def category_list(request):
    # Public sees only approved categories
    categories = Category.objects.filter(is_approved=True).order_by("name")

    form = None
    if request.user.is_staff:
        if request.method == "POST":
            form = CategoryForm(request.POST, request.FILES)
            if form.is_valid():
                category = form.save(commit=False)
                category.is_approved = False  # Pending admin approval
                category.save()
                messages.success(request, f"Category '{category.name}' submitted for approval.")
                return redirect("products:category_list")
        else:
            form = CategoryForm()

    return render(request, "products/category_list.html", {
        "categories": categories,
        "form": form,
    })


# =======================
# SELLER VIEWS
# =======================

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
@seller_required
def seller_product_list(request):
    """
    Seller dashboard product list.
    Fully safe for optional promotions.
    """

    # seller_required should already guarantee this
    seller = request.user

    products = (
        Product.objects
        .filter(seller=seller)
        .select_related("category")      # Promotion is OneToOne → DON'T select_related
        .prefetch_related("images")
    )

    return render(
        request,
        "products/seller_product_list.html",
        {
            "products": products
        }
    )


@login_required
@seller_required
def product_create(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        image_formset = ProductImageFormSet(request.POST, request.FILES)
        if form.is_valid() and image_formset.is_valid():
            product = form.save(commit=False)
            product.seller = request.user
            product.is_approved = False  # New products need approval
            product.save()
            image_formset.instance = product
            image_formset.save()
            messages.success(request, "Product submitted for approval!")
            return redirect("products:seller_product_list")
    else:
        form = ProductForm()
        image_formset = ProductImageFormSet()

    return render(request, "products/product_form.html", {
        "form": form,
        "image_formset": image_formset,
        "title": "Add New Product",
    })


@login_required
@seller_required
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk, seller=request.user)
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Product updated successfully.")
            return redirect("products:seller_products")
    else:
        form = ProductForm(instance=product)

    return render(request, "products/product_form.html", {
        "form": form,
        "title": "Edit Product",
    })


@login_required
@seller_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk, seller=request.user)
    if request.method == "POST":
        product.delete()
        messages.success(request, "Product deleted.")
        return redirect("products:seller_products")
    return render(request, "products/product_confirm_delete.html", {"product": product})


@login_required
@seller_required
def inventory(request):
    products = Product.objects.filter(seller=request.user).select_related("category")
    return render(request, "products/inventory.html", {"products": products})


from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F, FloatField
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import timedelta

from products.models import Product
from orders.models import OrderItem, Order
from users.decorators import seller_required
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F, FloatField
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, FloatField, Max
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import datetime, timedelta

from products.models import Product
from orders.models import OrderItem, Order
from users.decorators import seller_required


@login_required
@seller_required
def seller_reports(request):
    seller = request.user
    now = timezone.now()

    # -----------------------------
    # Date Range Filtering (FIXED & SAFE)
    # -----------------------------
    start_date = None
    end_date = None

    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if start_date_str:
        try:
            dt = datetime.strptime(start_date_str, '%Y-%m-%d')
            start_date = timezone.make_aware(dt.replace(hour=0, minute=0, second=0, microsecond=0))
        except ValueError:
            start_date = None

    if end_date_str:
        try:
            dt = datetime.strptime(end_date_str, '%Y-%m-%d')
            end_date = timezone.make_aware(dt.replace(hour=23, minute=59, second=59, microsecond=999999))
        except ValueError:
            end_date = None

    # Base queryset
    base_qs = OrderItem.objects.filter(
        product__seller=seller,
        order__is_paid=True
    )

    if start_date:
        base_qs = base_qs.filter(order__created_at__gte=start_date)
    if end_date:
        base_qs = base_qs.filter(order__created_at__lte=end_date)

    transactions = base_qs.select_related('order', 'product').prefetch_related('product__images')

    # -----------------------------
    # Basic Stats
    # -----------------------------
    products_count = Product.objects.filter(
        seller=seller,
        is_active=True,
        is_approved=True
    ).count()

    revenue_agg = transactions.aggregate(
        total_revenue=Sum(F('price') * F('quantity'), output_field=FloatField())
    )
    total_revenue = revenue_agg['total_revenue'] or 0.0

    paid_orders_qs = Order.objects.filter(
        items__product__seller=seller,
        is_paid=True
    )
    if start_date:
        paid_orders_qs = paid_orders_qs.filter(created_at__gte=start_date)
    if end_date:
        paid_orders_qs = paid_orders_qs.filter(created_at__lte=end_date)
    paid_orders_count = paid_orders_qs.distinct().count()

    average_order_value = total_revenue / paid_orders_count if paid_orders_count > 0 else 0.0

    # -----------------------------
    # Product Sales Summary
    # -----------------------------
    product_sales = (
        transactions
        .values('product__id', 'product__name')
        .annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum(F('price') * F('quantity'), output_field=FloatField()),
            last_sale_date=Max('order__created_at')
        )
        .order_by('-total_revenue')
    )

    # Preload product images efficiently
    product_ids = [item['product__id'] for item in product_sales if item['product__id']]
    product_map = {}
    if product_ids:
        products_with_images = Product.objects.filter(id__in=product_ids).prefetch_related('images')
        product_map = {p.id: p for p in products_with_images}

    sales = []
    for item in product_sales:
        product = product_map.get(item['product__id'])
        main_image = product.images.first().image.url if product and product.images.exists() else None

        percentage = (item['total_revenue'] / total_revenue * 100) if total_revenue > 0 else 0

        sales.append({
            'product__name': item['product__name'],
            'product_main_image': main_image,
            'total_quantity': item['total_quantity'],
            'total_revenue': item['total_revenue'],
            'percentage': round(percentage, 1),
            'last_sale_date': item['last_sale_date'],
        })

    # -----------------------------
    # Monthly Revenue Trend (Last 12 months or filtered range)
    # -----------------------------
    # Determine chart start: use filter start_date, otherwise go back ~12 months
    if start_date:
        chart_start_dt = start_date
    else:
        # Approximate 12 months ago
        approximate_year_ago = now - timedelta(days=365)
        chart_start_dt = approximate_year_ago.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Ensure timezone-aware
    if timezone.is_naive(chart_start_dt):
        chart_start_dt = timezone.make_aware(chart_start_dt)

    monthly_qs = (
        transactions
        .annotate(month=TruncMonth('order__created_at'))
        .values('month')
        .annotate(revenue=Sum(F('price') * F('quantity'), output_field=FloatField()))
        .filter(month__gte=chart_start_dt)
        .order_by('month')
    )

    monthly_map = {
        item['month'].strftime('%b %Y'): float(item['revenue'] or 0)
        for item in monthly_qs
    }

    monthly_labels = []
    monthly_revenue = []

    current = chart_start_dt.replace(day=1)
    while current <= now:
        label = current.strftime('%b %Y')
        monthly_labels.append(label)
        monthly_revenue.append(monthly_map.get(label, 0.0))

        # Move to next month
        next_month = current.month % 12 + 1
        next_year = current.year + (current.month // 12)
        current = current.replace(year=next_year, month=next_month, day=1)

    # -----------------------------
    # Top 10 Products for Chart
    # -----------------------------
    top_products = sales[:10]

    # -----------------------------
    # Context
    # -----------------------------
    context = {
        'products': products_count,
        'total_revenue': round(total_revenue, 2),
        'sales_count': paid_orders_count,
        'average_order_value': round(average_order_value, 2),

        'sales': sales,

        'monthly_labels': monthly_labels,
        'monthly_revenue': monthly_revenue,
        'top_product_names': [item['product__name'] for item in top_products],
        'top_product_revenue': [item['total_revenue'] for item in top_products],

        'current_start_date': start_date_str,
        'current_end_date': end_date_str,
    }

    return render(request, 'products/seller_reports.html', context)
@login_required
@seller_required
def seller_promotions(request):
    products = Product.objects.filter(seller=request.user).select_related("promotion")
    return render(request, "products/seller_promotions.html", {"products": products})


# =======================
# PROMOTION VIEWS
# =======================

@login_required
@seller_required
def promotions_list(request):
    products = Product.objects.filter(seller=request.user).select_related("promotion")
    return render(request, "products/promotions_list.html", {"products": products})


@login_required
@seller_required
def add_promotion(request, product_id):
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    promotion = product.promotion if hasattr(product, "promotion") else None

    if request.method == "POST":
        form = PromotionForm(request.POST, instance=promotion)
        if form.is_valid():
            promo = form.save(commit=False)
            promo.product = product
            promo.save()
            messages.success(request, f"Promotion updated for '{product.name}'")
            return redirect("products:promotions_list")
    else:
        form = PromotionForm(instance=promotion)

    return render(request, "products/add_promotion.html", {
        "form": form,
        "product": product,
    })


@login_required
@seller_required
def remove_promotion(request, product_id):
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    promotion = get_object_or_404(Promotion, product=product)

    if request.method == "POST":
        promotion.delete()
        messages.success(request, "Promotion removed.")
    else:
        messages.info(request, "Promotion removal cancelled.")

    return redirect("products:promotions_list")


# products/views.py

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils.text import slugify

from users.decorators import seller_required
from .forms import CategoryForm
from .models import Category

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils.text import slugify
from django.http import HttpResponseForbidden

from .forms import CategoryForm
from .models import Category
from users.decorators import seller_required


@login_required
@seller_required
def category_create(request):
    """
    Sellers can propose a new category.
    Categories created by sellers require admin approval.
    Admins can create categories that are auto-approved.
    """

    # Extra safety (defense in depth)
    if not request.user.is_seller and not request.user.is_staff:
        return HttpResponseForbidden("You are not allowed to create categories.")

    if request.method == "POST":
        form = CategoryForm(request.POST, request.FILES)

        if form.is_valid():
            category = form.save(commit=False)

            # 🔍 Prevent duplicate category names (case-insensitive)
            if Category.objects.filter(name__iexact=category.name).exists():
                messages.error(
                    request,
                    "A category with this name already exists or is pending approval."
                )
                return render(request, "products/category_form.html", {
                    "form": form,
                    "title": "Propose New Category",
                    "subtitle": "Suggest a new category for Style Bazaar.",
                })

            # 🔗 Auto-generate unique slug
            if not category.slug:
                base_slug = slugify(category.name)
                slug = base_slug
                counter = 1
                while Category.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                category.slug = slug

            # 👑 Admin vs Seller behavior
            if request.user.is_staff:
                category.is_approved = True
                messages.success(
                    request,
                    f"Category '{category.name}' created and published successfully."
                )
            else:
                category.is_approved = False
                messages.success(
                    request,
                    f"Category '{category.name}' submitted successfully! "
                    "It will be reviewed by admin before going live."
                )

            # 🧾 Track who requested it
            category.requested_by = request.user

            category.save()

            # 🚀 Redirect logic
            if request.user.is_staff:
                return redirect("products:category_list")
            return redirect("seller_dashboard")

        else:
            messages.error(request, "Please correct the errors below.")

    else:
        form = CategoryForm()

    return render(request, "products/category_form.html", {
        "form": form,
        "title": "Add Category" if request.user.is_staff else "Propose New Category",
        "subtitle": (
            "Create a new category for the store."
            if request.user.is_staff else
            "Suggest a new category for Style Bazaar. "
            "It will be reviewed and approved by admin before going live."
        ),
        "is_seller": request.user.is_seller,
        "is_admin": request.user.is_staff,
    })

@login_required
@seller_required
def category_update(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Category updated.")
            return redirect("products:category_list")
    else:
        form = CategoryForm(instance=category)
    return render(request, "products/category_form.html", {
        "form": form,
        "title": "Edit Category",
    })


@login_required
@seller_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        category.delete()
        messages.success(request, "Category deleted.")
        return redirect("products:category_list")
    return render(request, "products/category_confirm_delete.html", {"category": category})


# =======================
# BUYER-FACING PRODUCT LIST (Public Shopping View)
# =======================
def buyer_product_list(request):
    """
    Dedicated product list for buyers — clean, grid layout, with search and category filters.
    Only shows active and approved products.
    """
    category_slug = request.GET.get("category")
    query = request.GET.get("q")
    min_price = request.GET.get("min_price")
    max_price = request.GET.get("max_price")

    # Base queryset: only visible products
    products = Product.objects.filter(
        is_active=True,
        is_approved=True
    ).select_related("category", "seller").prefetch_related("images").order_by("-created_at")

    selected_category = None

    # Category filter
    if category_slug:
        selected_category = get_object_or_404(Category, slug=category_slug, is_approved=True)
        products = products.filter(category=selected_category)

    # Search filter
    if query:
        products = products.filter(name__icontains=query)

    # Price range filter
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)

    # Get all categories for sidebar/filter
    categories = Category.objects.filter(is_approved=True).order_by("name")

    context = {
        "products": products,
        "categories": categories,
        "selected_category": selected_category,
        "search_query": query,
        "min_price": min_price,
        "max_price": max_price,
    }
    return render(request, "products/buyer_product_list.html", context)