from .models import OrderItem

def seller_notifications(request):
    if request.user.is_authenticated and request.user.is_seller():
        count = OrderItem.objects.filter(
            product__seller=request.user,
            order__is_paid=True
        ).count()
        return {"new_orders_count": count}
    return {}
