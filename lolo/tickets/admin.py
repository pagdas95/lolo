from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from .models import TicketPackage, Order, TicketTransaction

@admin.register(TicketPackage)
class TicketPackageAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'price',
        'number_of_tickets',
        'is_active',
        'created_at',
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = [
        (None, {
            'fields': ('name', 'description', 'is_active')
        }),
        (_('Pricing Details'), {
            'fields': ('price', 'number_of_tickets')
        }),
        (_('Stripe Details'), {
            'fields': ('stripe_price_id',),
            'classes': ('collapse',),
            'description': _('Stripe integration details')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        })
    ]

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'user',
        'ticket_package',
        'status',
        'formatted_amount',
        'created_at',
    ]
    list_filter = ['status', 'created_at']
    search_fields = [
        'user__username',
        'user__email',
        'stripe_checkout_session_id',
        'stripe_payment_intent_id'
    ]
    readonly_fields = [
        'stripe_checkout_session_id',
        'stripe_payment_intent_id',
        'created_at',
        'updated_at'
    ]

    def formatted_amount(self, obj):
        return f"${obj.ticket_package.price}"
    formatted_amount.short_description = _("Amount")

    fieldsets = [
        (None, {
            'fields': ('user', 'ticket_package', 'status')
        }),
        (_('Stripe Details'), {
            'fields': (
                'stripe_checkout_session_id',
                'stripe_payment_intent_id'
            ),
            'classes': ('collapse',),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        })
    ]

@admin.register(TicketTransaction)
class TicketTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'transaction_type',
        'number_of_tickets',
        'balance_after',
        'created_at',
    ]
    list_filter = ['transaction_type', 'created_at']
    search_fields = [
        'user__username',
        'user__email',
        'notes'
    ]
    readonly_fields = ['balance_after', 'created_at']

    def has_add_permission(self, request):
        # Prevent manual creation of transactions
        return False

    def has_change_permission(self, request, obj=None):
        # Prevent editing of transactions
        return False

    fieldsets = [
        (None, {
            'fields': (
                'user',
                'order',
                'transaction_type',
                'number_of_tickets',
                'balance_after'
            )
        }),
        (_('Additional Information'), {
            'fields': ('notes',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at',),
            'classes': ('collapse',),
        })
    ]