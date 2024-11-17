from django.contrib.auth.models import AbstractUser
from django.db.models import CharField, PositiveIntegerField
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    """
    Default custom user model for lolo.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """

    # First and last name do not cover name patterns around the globe
    name = CharField(_("Name of User"), blank=True, max_length=255)
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]
    tickets = PositiveIntegerField(_("Tickets"), default=0)
    bio = models.TextField(_("Bio"), blank=True, max_length=500)
    avatar = models.ImageField(
        _("Avatar"), 
        upload_to='user_avatars/', 
        blank=True, 
        null=True
    )
    
    first_time_login = models.BooleanField(
        _("First Time Login"),
        default=True,  # Everyone starts with True (they're new!)
        help_text=_("Indicates if this is the user's first time logging in")
    )    
    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"username": self.username})
