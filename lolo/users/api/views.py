from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.mixins import UpdateModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from dj_rest_auth.registration.views import VerifyEmailView
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils.translation import gettext_lazy as _
from lolo.users.models import User
from allauth.account.models import EmailAddress

from .serializers import UserSerializer, UserProfileUpdateSerializer


class UserViewSet(RetrieveModelMixin, ListModelMixin, UpdateModelMixin, GenericViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.all()
    lookup_field = "username"
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_queryset(self, *args, **kwargs):
        assert isinstance(self.request.user.id, int)
        return self.queryset.filter(id=self.request.user.id)

    @action(detail=False)
    def me(self, request):
        """
        This endpoint shows the current user's information,
        including email verification status
        """
        user = request.user
        serializer = UserSerializer(user, context={"request": request})
        
        # Get email verification status from allauth
        email_status = EmailAddress.objects.filter(user=user).first()
        
        # Combine user data with email status
        data = serializer.data
        data['email_verification'] = {
            'email': user.email,
            'verified': email_status.verified if email_status else False,
            'primary': email_status.primary if email_status else False,
        }
        
        return Response(data)

    @action(detail=False)
    def email_status(self, request):
        """
        A dedicated endpoint just for checking email status
        Like looking at just the "verified" checkmark
        """
        user = request.user
        email_status = EmailAddress.objects.filter(user=user).first()
        
        return Response({
            'email': user.email,
            'verified': email_status.verified if email_status else False,
            'primary': email_status.primary if email_status else False
        })
    
    


    @action(detail=False, methods=['patch'])
    def update_profile(self, request):
        """Update user profile (name, bio)"""
        serializer = UserProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                UserSerializer(request.user, context={"request": request}).data
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def upload_avatar(self, request):
        """Handle avatar upload separately"""
        if 'avatar' not in request.FILES:
            return Response(
                {'error': _('No avatar file provided')},
                status=status.HTTP_400_BAD_REQUEST
            )

        request.user.avatar = request.FILES['avatar']
        request.user.save()
        return Response(
            UserSerializer(request.user, context={"request": request}).data
        )

    @action(detail=False)
    def tickets(self, request):
        """Get user's ticket balance"""
        return Response({
            'tickets': request.user.tickets
        })
    
class CustomVerifyEmailView(VerifyEmailView):
    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except Exception as e:
            return Response(
                {"detail": "Invalid verification key or link expired."},
                status=status.HTTP_400_BAD_REQUEST
            )

    def get(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except Exception as e:
            return Response(
                {"detail": "Invalid verification key or link expired."},
                status=status.HTTP_400_BAD_REQUEST
            )

    
@api_view(['GET', 'POST'])
def debug_verification(request, key):
    try:
        # Try to get the email confirmation
        email_confirmation = EmailConfirmationHMAC.from_key(key)
        if email_confirmation:
            email_confirmation.confirm(request)
            return Response({
                "detail": _("Email successfully confirmed"),
                "email": email_confirmation.email_address.email
            })
    except Exception as e:
        return Response({
            "detail": _("Invalid key"),
            "error": str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

