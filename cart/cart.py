from decimal import Decimal
from products.models import Product
from orders.models import Coupon  # Optional: for future coupon support


class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get("cart")

        if not cart:
            cart = self.session["cart"] = {}

        self.cart = cart

        # Coupon support
        self.coupon_id = self.session.get("coupon_id")

    # -------------------------
    # ADD PRODUCT
    # -------------------------
    def add(self, product, quantity=1, price=None, override_quantity=False):
        """
        Add a product to the cart.
        - If price is provided, use it (e.g., snapshot at add time)
        - Otherwise, use product's current_price at the moment of adding
        """
        product_id = str(product.id)
        price_to_use = Decimal(price) if price is not None else product.current_price

        if product_id not in self.cart:
            self.cart[product_id] = {
                "quantity": 0,
                "price": str(price_to_use),  # Store as string for session safety
            }

        if override_quantity:
            self.cart[product_id]["quantity"] = quantity
        else:
            self.cart[product_id]["quantity"] += quantity

        # Remove if quantity drops to 0 or below
        if self.cart[product_id]["quantity"] <= 0:
            self.remove(product)

        self.save()

    # -------------------------
    # SAVE SESSION
    # -------------------------
    def save(self):
        self.session.modified = True

    # -------------------------
    # REMOVE PRODUCT
    # -------------------------
    def remove(self, product):
        product_id = str(product.id)
        if product_id in self.cart:
            del self.cart[product_id]
            self.save()

    # -------------------------
    # ITERATE CART (SAFE & UP-TO-DATE)
    # -------------------------
    def __iter__(self):
        """
        Yield cart items with fresh product data and current pricing.
        Uses Product.current_price → always correct (promotion, manual discount, or regular).
        """
        product_ids = self.cart.keys()
        if not product_ids:
            return

        # Fetch products efficiently (no need for select_related("promotion"))
        products = Product.objects.filter(id__in=product_ids).prefetch_related("images")

        products_dict = {str(p.id): p for p in products}

        for item in self.cart.values():
            product_id_str = item.get("product_id") or list(self.cart.keys())[list(self.cart.values()).index(item)]
            product = products_dict.get(product_id_str)

            if product:
                # Attach full product object
                item["product"] = product

                # Current unit price (refreshed every time cart is viewed)
                current_unit_price = product.current_price

                # Stored price when item was added (for reference)
                stored_price = Decimal(item["price"])

                item["unit_price"] = float(current_unit_price)
                item["total_price"] = float(current_unit_price * item["quantity"])

                # Useful flags for template
                item["has_active_promotion"] = product.has_active_promotion
                item["active_promotion"] = product.active_promotion  # Safe: returns None if no active promo
                item["original_price"] = float(product.price) if product.price > current_unit_price else None

            else:
                # Product no longer exists — fallback to stored data
                stored_price = Decimal(item["price"])
                item["unit_price"] = float(stored_price)
                item["total_price"] = float(stored_price * item["quantity"])
                item["has_active_promotion"] = False
                item["active_promotion"] = None
                item["original_price"] = None

            yield item

    # -------------------------
    # CART LENGTH
    # -------------------------
    def __len__(self):
        return sum(item["quantity"] for item in self.cart.values())

    # -------------------------
    # SUBTOTAL (based on current prices)
    # -------------------------
    def get_subtotal(self):
        return sum(
            Decimal(item["unit_price"]) * item["quantity"]
            for item in self
        )

    # -------------------------
    # TOTAL PRICE (after coupon)
    # -------------------------
    def get_total_price(self):
        subtotal = self.get_subtotal()
        discount = self.get_discount()
        return max(subtotal - discount, Decimal("0"))

    # -------------------------
    # CLEAR CART
    # -------------------------
    def clear(self):
        self.session["cart"] = {}
        if "coupon_id" in self.session:
            del self.session["coupon_id"]
        self.save()

    # -------------------------
    # COUPON SUPPORT
    # -------------------------
    @property
    def coupon(self):
        if self.coupon_id:
            try:
                return Coupon.objects.get(id=self.coupon_id)
            except Coupon.DoesNotExist:
                self.coupon_id = None
                self.save()
        return None

    def apply_coupon(self, coupon):
        if coupon and getattr(coupon, "is_valid", lambda: True)():
            self.coupon_id = coupon.id
            self.save()
            return True
        return False

    def get_discount(self):
        if self.coupon:
            discount_percent = Decimal(getattr(self.coupon, "discount_percent", 0))
            return (self.get_subtotal() * discount_percent) / Decimal("100")
        return Decimal("0")

    def get_total_price_after_discount(self):
        return self.get_total_price()

    # -------------------------
    # HELPER: Get single item
    # -------------------------
    def get_item(self, product_id):
        product_id_str = str(product_id)
        if product_id_str in self.cart:
            return self.cart[product_id_str]
        return None