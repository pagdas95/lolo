# config/api_router.py
from django.conf import settings
from rest_framework.routers import DefaultRouter, SimpleRouter
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from lolo.users.api.views import UserViewSet
from lolo.tournament.api.views import (
    CategoryViewSet,
    TournamentViewSet,
    VideoSubmissionViewSet,
    ParticipationViewSet,
    UserTournamentProfileViewSet,
)
class AuthenticatedRouter(DefaultRouter if settings.DEBUG else SimpleRouter):
    def get_api_root_view(self, api_urls=None):
        view = super().get_api_root_view(api_urls=api_urls)
        view.cls.authentication_classes = [TokenAuthentication]
        view.cls.permission_classes = [IsAuthenticated]
        return view

router = AuthenticatedRouter()
if settings.DEBUG:
    router = DefaultRouter()
else:
    router = SimpleRouter()

router.register("users", UserViewSet)
router.register("categories", CategoryViewSet)
router.register("tournaments", TournamentViewSet)
router.register("videos", VideoSubmissionViewSet)
router.register('profiles', UserTournamentProfileViewSet, basename='user-profile')


app_name = "api"
urlpatterns = router.urls