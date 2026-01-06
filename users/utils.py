def get_dashboard_url(user):
    if user.is_buyer():
        return 'buyer_dashboard'
    elif user.is_seller():
        return 'seller_dashboard'
    return 'admin_dashboard'
