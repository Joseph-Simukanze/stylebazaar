def stripe_webhook(request):
    payload = request.body
    event = stripe.Event.construct_from(
        json.loads(payload), stripe.api_key
    )

    if event.type == "payment_intent.succeeded":
        intent = event.data.object
        order = Order.objects.get(
            stripe_payment_intent=intent.id
        )
        order.paid = True
        order.save()
