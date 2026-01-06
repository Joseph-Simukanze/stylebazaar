from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST

from products.models import Product
from .cart import Cart


# ====================
# CART VIEWS
# ====================

def cart_detail(request):
    """Display the current cart contents with up-to-date prices"""
    cart = Cart(request)

    # Update each item's price to reflect current product price (in case promotion started/ended/changed)
    for item in cart:
        item.update({
            'unit_price': item['product'].current_price,
            'total_price': item['product'].current_price * item['quantity']
        })

    return render(request, "cart/cart_detail.html", {"cart": cart})


@require_POST
def cart_add(request, product_id):
    """
    Add a product to the cart using the CURRENT correct price.
    Only active, approved, and in-stock products can be added.
    """
    cart = Cart(request)

    product = get_object_or_404(
        Product,
        id=product_id,
        is_active=True,
        is_approved=True,
        stock__gt=0  # At least some stock
    )

    # Get quantity from form
    try:
        quantity = int(request.POST.get("quantity", 1))
        quantity = max(1, quantity)
    except (TypeError, ValueError):
        quantity = 1

    # IMPORTANT: Always use the current_price at the time of adding
    price_to_use = product.current_price

    cart.add(
        product=product,
        quantity=quantity,
        price=price_to_use,  # Snapshot of current price
        override_quantity=False
    )

    # Success message with promotion indicator
    if product.has_active_promotion:
        promo_text = " (on sale!)"
    elif product.discounted_price is not None:
        promo_text = " (special price)"
    else:
        promo_text = ""

    messages.success(
        request,
        f"{quantity} × {product.name} added to your cart{promo_text}!"
    )

    return redirect("cart_detail")


def cart_remove(request, product_id):
    """Remove a product completely from the cart"""
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)

    cart.remove(product)
    messages.success(request, f"{product.name} removed from your cart.")

    return redirect("cart_detail")


@require_POST
@login_required
def cart_update(request, product_id):
    """Increase or decrease item quantity in cart"""
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)

    action = request.POST.get("action")

    if action == "increase":
        if product.stock <= 0:
            messages.error(request, f"{product.name} is currently out of stock.")
            return redirect("cart_detail")

        # Add one more using the CURRENT price (in case promotion changed since item was added)
        cart.add(
            product=product,
            quantity=1,
            price=product.current_price,
            override_quantity=False
        )
        messages.success(request, f"Quantity of {product.name} increased.")

    elif action == "decrease":
        current_item = cart.get_item(product_id)

        if current_item and current_item["quantity"] > 1:
            # Decrease by 1 (uses stored price from when it was added)
            cart.add(
                product=product,
                quantity=-1,
                price=current_item["price"],  # Keep original price for fairness
                override_quantity=False
            )
            messages.success(request, f"Quantity of {product.name} decreased.")
        else:
            # If quantity becomes 0, remove entirely
            cart.remove(product)
            messages.info(request, f"{product.name} removed from cart.")

    return redirect("cart_detail")


@login_required
def cart_clear(request):
    """Empty the entire cart"""
    cart = Cart(request)

    if len(cart) > 0:
        cart.clear()
        messages.success(request, "Your cart has been emptied.")
    else:
        messages.info(request, "Your cart was already empty.")

    return redirect("cart_detail")