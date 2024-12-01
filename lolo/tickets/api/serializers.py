from rest_framework import serializers
from ..models import TicketPackage, Order, TicketTransaction

class TicketPackageSerializer(serializers.ModelSerializer):
    checkout_url = serializers.URLField(source='get_checkout_url', read_only=True)
    
    class Meta:
        model = TicketPackage
        fields = ['id', 'name', 'number_of_tickets', 'price', 
                 'description', 'checkout_url']

class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['id', 'ticket_package', 'status', 'created_at']
        read_only_fields = ['status']