from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

class TicketPackage(models.Model):
    """
    Represents different ticket packages that users can purchase
    """
    name = models.CharField(_("Package Name"), max_length=100)
    number_of_tickets = models.PositiveIntegerField(_("Number of Tickets"))
    price = models.DecimalField(_("Price"), max_digits=10, decimal_places=2)
    description = models.TextField(_("Description"), blank=True)
    is_active = models.BooleanField(_("Is Active"), default=True)
    stripe_price_id = models.CharField(
        _("Stripe Price ID"),
        max_length=100,
        blank=True,
        help_text=_("The Stripe Price ID for this package")
    )
    
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.number_of_tickets} tickets for ${self.price}"

    def get_checkout_url(self):
        return reverse('tickets:package-create-checkout-session', kwargs={'pk': self.pk})

class Order(models.Model):
    """
    Represents a ticket purchase order
    """
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
        ('cancelled', _('Cancelled')),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    ticket_package = models.ForeignKey(
        TicketPackage,
        on_delete=models.PROTECT,
        related_name='orders'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    stripe_checkout_session_id = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )
    stripe_payment_intent_id = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order {self.id} by {self.user.username}"

class TicketTransaction(models.Model):
    """
    Tracks ticket additions and deductions for users
    """
    TRANSACTION_TYPES = [
        ('purchase', _('Purchase')),
        ('use', _('Use')),
        ('refund', _('Refund')),
        ('bonus', _('Bonus')),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ticket_transactions'
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ticket_transactions'
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    number_of_tickets = models.IntegerField()
    balance_after = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.transaction_type}: {self.number_of_tickets} tickets for {self.user.username}"