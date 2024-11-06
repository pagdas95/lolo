# lolo/tournament/api/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from ..models import Category, Tournament, VideoSubmission, Participation, Vote
from .serializers import (
    CategorySerializer,
    TournamentListSerializer,
    TournamentDetailSerializer,
    VideoSubmissionSerializer,
    ParticipationSerializer,
    VoteSerializer
)
from .permissions import IsAdminOrReadOnly, IsOwnerOrReadOnly
from .pagination import CustomPagination, VideosPagination
from django.db.models import Count, F
from rest_framework import filters
from django_filters import rest_framework as django_filters



class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]

class TournamentFilter(django_filters.FilterSet):
    category = django_filters.NumberFilter(field_name='category__id')
    is_active = django_filters.BooleanFilter(method='filter_active')
    min_participants = django_filters.NumberFilter(
        method='filter_by_participants',
        label='Minimum participants'
    )
    sort_by = django_filters.ChoiceFilter(
        choices=(
            ('most_viewed', 'Most Viewed'),
            ('most_participants', 'Most Participants'),
            ('most_votes', 'Most Votes'),
            ('newest', 'Newest'),
            ('oldest', 'Oldest'),
        ),
        method='sort_tournaments'
    )

    class Meta:
        model = Tournament
        fields = ['category', 'is_final_tournament', 'is_active']

    def filter_active(self, queryset, name, value):
        now = timezone.now()
        if value:
            return queryset.filter(start_time__lte=now, end_time__gte=now)
        return queryset

    def filter_by_participants(self, queryset, name, value):
        return queryset.annotate(
            participant_count=Count('participations')
        ).filter(participant_count__gte=value)

    def sort_tournaments(self, queryset, name, value):
        if value == 'most_viewed':
            return queryset.order_by('-views_count')
        elif value == 'most_participants':
            return queryset.annotate(
                participant_count=Count('participations')
            ).order_by('-participant_count')
        elif value == 'most_votes':
            return queryset.annotate(
                votes_count=Count('votes')
            ).order_by('-votes_count')
        elif value == 'newest':
            return queryset.order_by('-created_at')
        elif value == 'oldest':
            return queryset.order_by('created_at')
        return queryset
    
class TournamentViewSet(viewsets.ModelViewSet):
    queryset = Tournament.objects.all()
    pagination_class = CustomPagination
    filter_backends = [
        django_filters.DjangoFilterBackend,
        filters.SearchFilter
    ]
    filterset_class = TournamentFilter
    search_fields = ['title', 'description']

    def get_serializer_class(self):
        if self.action == 'list':
            return TournamentListSerializer
        return TournamentDetailSerializer

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAdminUser]
        elif self.action in ['enter_tournament', 'vote']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.AllowAny]
        return [permission() for permission in permission_classes]

    def retrieve(self, request, *args, **kwargs):
        """
        Get tournament details and increment view count
        """
        instance = self.get_object()
        # Increment views only for non-creator views
        if not request.user.is_authenticated or request.user != instance.created_by:
            Tournament.objects.filter(pk=instance.pk).update(
                views_count=F('views_count') + 1
            )
            instance.refresh_from_db()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def enter_tournament(self, request, pk=None):
        """
        Enter a tournament by submitting a video
        """
        tournament = self.get_object()
        user = request.user

        # Validation checks
        if user.tickets < tournament.entry_fee:
            return Response(
                {"error": f"Insufficient tickets. You need {tournament.entry_fee} tickets to enter."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if Participation.objects.filter(user=user, tournament=tournament).exists():
            return Response(
                {"error": "You have already entered this tournament"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not tournament.is_active:
            return Response(
                {"error": "This tournament is not currently active"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if tournament.participant_limit and \
           Participation.objects.filter(tournament=tournament).count() >= tournament.participant_limit:
            return Response(
                {"error": "Tournament has reached maximum participants"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                video_serializer = VideoSubmissionSerializer(data=request.data)
                if video_serializer.is_valid():
                    video = video_serializer.save(user=user)
                    participation = Participation.objects.create(
                        user=user,
                        tournament=tournament,
                        video_submission=video
                    )
                    user.tickets -= tournament.entry_fee
                    user.save()

                    return Response(
                        ParticipationSerializer(participation).data,
                        status=status.HTTP_201_CREATED
                    )
                return Response(
                    video_serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'])
    def participants(self, request, pk=None):
        """
        Get paginated list of tournament participants
        """
        tournament = self.get_object()
        participations = Participation.objects.filter(
            tournament=tournament
        ).select_related('user', 'video_submission')
        
        # Sorting
        sort_by = request.query_params.get('sort', '-created_at')
        sort_options = {
            'most_votes': '-votes_received',
            'most_viewed': '-video_submission__views_count',
            'newest': '-created_at',
            'oldest': 'created_at'
        }
        sort_field = sort_options.get(sort_by, '-created_at')
        participations = participations.order_by(sort_field)

        # Pagination
        page = self.paginate_queryset(participations)
        if page is not None:
            serializer = ParticipationSerializer(page, many=True)
            return self.get_paginated_response({
                'tournament_info': {
                    'title': tournament.title,
                    'total_participants': participations.count(),
                    'views_count': tournament.views_count,
                    'total_votes': Vote.objects.filter(tournament=tournament).count(),
                },
                'participants': serializer.data
            })

        serializer = ParticipationSerializer(participations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def vote(self, request, pk=None):
        """
        Vote for a participant in the tournament
        """
        tournament = self.get_object()
        user = request.user
        participation_id = request.data.get('participation_id')

        if not participation_id:
            return Response(
                {"error": "participation_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            participation = Participation.objects.get(
                id=participation_id,
                tournament=tournament
            )
        except Participation.DoesNotExist:
            return Response(
                {"error": "Invalid participation ID"},
                status=status.HTTP_404_NOT_FOUND
            )

        if participation.user == user:
            return Response(
                {"error": "You cannot vote for your own submission"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if Vote.objects.filter(voter=user, tournament=tournament).exists():
            return Response(
                {"error": "You have already voted in this tournament"},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            Vote.objects.create(
                voter=user,
                participation=participation,
                tournament=tournament
            )
            participation.votes_received += 1
            participation.save()

            return Response({
                "message": "Vote recorded successfully",
                "participation": ParticipationSerializer(participation).data
            }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def standings(self, request, pk=None):
        """
        Get tournament standings ordered by votes
        """
        tournament = self.get_object()
        participations = Participation.objects.filter(
            tournament=tournament
        ).select_related('user', 'video_submission').order_by('-votes_received')

        page = self.paginate_queryset(participations)
        if page is not None:
            serializer = ParticipationSerializer(page, many=True)
            return self.get_paginated_response({
                'tournament_info': {
                    'title': tournament.title,
                    'total_participants': participations.count(),
                    'views_count': tournament.views_count,
                    'total_votes': Vote.objects.filter(tournament=tournament).count(),
                },
                'standings': serializer.data
            })

        serializer = ParticipationSerializer(participations, many=True)
        return Response(serializer.data)
        
class VideoSubmissionViewSet(viewsets.ModelViewSet):
    queryset = VideoSubmission.objects.all()
    serializer_class = VideoSubmissionSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class ParticipationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ParticipationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Participation.objects.filter(tournament_id=self.kwargs['tournament_pk'])