import stripe
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from ..models import TicketPackage, Order, TicketTransaction
from .serializers import TicketPackageSerializer, OrderSerializer

stripe.api_key = settings.STRIPE_SECRET_KEY

class TicketPackageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TicketPackage.objects.filter(is_active=True)
    serializer_class = TicketPackageSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['post'])
    def create_checkout_session(self, request, pk=None):
        package = self.get_object()
        return_url = request.data.get('return_url')
        
        if not return_url:
            return Response(
                {'error': 'return_url is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create order first
        order = Order.objects.create(
            user=request.user,
            ticket_package=package,
            status='pending'
        )

        try:
            # Get the auth token for the user
            auth_token = request.auth.key if hasattr(request, 'auth') and request.auth else None
            
            # Include the token in the success URL
            success_url = (
                f"{return_url}?status=success"
                f"&session_id={{CHECKOUT_SESSION_ID}}"
                f"&token={auth_token if auth_token else ''}"
                f"&return_url={return_url}"
            )
            
            # Create Stripe Checkout Session
            checkout_session = stripe.checkout.Session.create(
                client_reference_id=request.user.id,
                customer_email=request.user.email,
                allow_promotion_codes=True,
                invoice_creation={
                    'enabled': True,
                    'invoice_data': {
                        'description': f'Purchase of {package.name} - {package.number_of_tickets} Tickets',
                        'custom_fields': [
                            {'name': 'Order ID', 'value': str(order.id)},
                            {'name': 'Package', 'value': package.name}
                        ],
                        'footer': 'Thank you for your purchase!'
                    }
                },
                line_items=[{
                    'price_data': {
                        'currency': 'eur',
                        'product_data': {
                            'name': package.name,
                            'description': f'{package.number_of_tickets} Tickets',
                        },
                        'unit_amount': int(package.price * 100),
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=f"{return_url}?status=cancelled",
                payment_method_types=['card'],
                metadata={
                    'order_id': order.id,
                    'package_id': package.id,
                    'number_of_tickets': package.number_of_tickets,
                    'return_url': return_url
                }
            )
            
            order.stripe_checkout_session_id = checkout_session.id
            order.save()

            return Response({
                'checkout_url': checkout_session.url
            })

        except Exception as e:
            order.status = 'failed'
            order.save()
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class StripeWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.SignatureVerificationError as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # Handle the checkout.session.completed event
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            
            # Retrieve the order
            order = Order.objects.get(
                stripe_checkout_session_id=session.id
            )
            
            if order.status == 'completed':
                return Response(status=status.HTTP_200_OK)
            
            # Update order status
            order.status = 'completed'
            order.stripe_payment_intent_id = session.payment_intent
            order.save()

            # Add tickets to user's balance
            package = order.ticket_package
            user = order.user
            
            # Create ticket transaction
            TicketTransaction.objects.create(
                user=user,
                order=order,
                transaction_type='purchase',
                number_of_tickets=package.number_of_tickets,
                balance_after=user.tickets + package.number_of_tickets,
                notes=f"Purchase of {package.name} package"
            )
            
            # Update user's ticket balance
            user.tickets += package.number_of_tickets
            user.save()

        return Response(status=status.HTTP_200_OK)