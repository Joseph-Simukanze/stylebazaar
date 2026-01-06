from django.urls import path
from . import views
from .views import confirm_payment,simulate_payment

app_name = "payments"

urlpatterns = [
    path("<int:order_id>/", views.payment, name="payment"),
    path('payment-methods/', views.payment_methods_view, name='payment_methods'),
   path('order/<int:order_id>/confirm-payment/', confirm_payment, name='confirm_payment'),
   path('order/<int:order_id>/simulate-payment/', simulate_payment, name='simulate_payment'),
]