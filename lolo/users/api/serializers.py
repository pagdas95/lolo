from rest_framework import serializers

from lolo.users.models import User


class UserSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = ["username", "name", "url", "tickets", "bio", "avatar",]
        read_only_fields = ('email',)
        extra_kwargs = {
            "url": {"view_name": "api:user-detail", "lookup_field": "username"},
        }

# Optional: Create a separate serializer for profile updates
class UserProfileUpdateSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = ["name", "bio", "avatar"]