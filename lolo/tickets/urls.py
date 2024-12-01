from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api.views import TicketPackageViewSet, StripeWebhookView
from django.http import JsonResponse

def success_view(request):
    return JsonResponse({'status': 'success', 'session_id': request.GET.get('session_id')})

def cancel_view(request):
    return JsonResponse({'status': 'cancelled'})

app_name = "tickets"

router = DefaultRouter()
router.register(r'packages', TicketPackageViewSet, basename='package')

urlpatterns = [
    path('', include(router.urls)),
    path('webhook/', StripeWebhookView.as_view(), name='webhook'),
    path('success/', success_view, name='success'),
    path('cancelled/', cancel_view, name='cancelled'),
]