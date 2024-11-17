# config/api_router.py
from django.conf import settings
from rest_framework.routers import DefaultRouter, SimpleRouter

from lolo.users.api.views import UserViewSet
from lolo.tournament.api.views import (
    CategoryViewSet,
    TournamentViewSet,
    VideoSubmissionViewSet,
    ParticipationViewSet,
    UserTournamentProfileViewSet,
)

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