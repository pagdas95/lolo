# lolo/tournament/api/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from ..models import Category, Tournament, VideoSubmission, Participation, Vote, VideoReport, Sponsor
from .serializers import (
    CategorySerializer,
    TournamentListSerializer,
    TournamentDetailSerializer,
    VideoSubmissionSerializer,
    ParticipationSerializer,
    VoteSerializer,
    VideoReportSerializer,
    SponsorSerializer,
    SponsorDetailSerializer
)
from .permissions import IsAdminOrReadOnly, IsOwnerOrReadOnly
from .pagination import CustomPagination, VideosPagination
from django.db.models import Count, F, Q
from rest_framework import filters
from django_filters import rest_framework as django_filters
from random import sample
from django.contrib.auth import get_user_model


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    # permission_classes = [IsAdminOrReadOnly]
    permission_classes = [permissions.IsAuthenticated]
    
    # Remove pagination for this viewset
    pagination_class = None

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class TournamentFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(method='filter_categories')
    category_name = django_filters.CharFilter(
        field_name='category__name',
        lookup_expr='icontains'
    )
    is_active = django_filters.BooleanFilter(method='filter_active')
    featured = django_filters.BooleanFilter(field_name='featured')
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
            ('featured', 'Featured First'),
        ),
        method='sort_tournaments'
    )

    class Meta:
        model = Tournament
        fields = ['category', 'category_name', 'is_final_tournament', 'is_active', 'featured']

    def filter_categories(self, queryset, name, value):
        """Handle multiple category IDs"""
        if not value:
            return queryset
        
        # Split the comma-separated values and convert to integers
        category_ids = [int(cat_id) for cat_id in value.split(',') if cat_id.strip().isdigit()]
        
        if category_ids:
            return queryset.filter(category_id__in=category_ids)
        return queryset

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
        if value == 'category':
            return queryset.order_by('category__name')        
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
        elif value == 'featured':
            return queryset.order_by('-featured', '-start_time')
        
        return queryset
    
class TournamentViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
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
        """Ensure authentication for all endpoints"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Increment views only for non-creator views
        if not request.user.is_authenticated or request.user != instance.created_by:
            Tournament.objects.filter(pk=instance.pk).update(
                views_count=F('views_count') + 1
            )
            instance.refresh_from_db()

        # Get participants with user details
        participants = Participation.objects.filter(
            tournament=instance
        ).select_related('user', 'video_submission').order_by('-created_at')
        
        # Get base tournament data
        data = self.get_serializer(instance).data
        
        # Add participants data
        data['participants'] = [{
            'id': p.id,
            'username': p.user.username,
            'avatar': request.build_absolute_uri(p.user.avatar.url) if p.user.avatar else None,
            'video_title': p.video_submission.title,
            'votes_received': p.votes_received,
            'is_finalist': p.is_finalist,
            'created_at': p.created_at
        } for p in participants]

        # Check if user is a participant
        is_participant = Participation.objects.filter(
            user=request.user, 
            tournament=instance
        ).exists()

        # Check if user has voted
        vote = Vote.objects.filter(
            voter=request.user, 
            tournament=instance
        ).select_related('participation__video_submission', 'participation__user').first()
        
        # Can vote if: is a participant AND hasn't voted yet
        can_vote = is_participant and not vote
        
        data['voting_status'] = {
            'has_voted': bool(vote),
            'can_vote': can_vote,
            'is_participant': is_participant
        }
        
        if vote:
            data['voting_status']['vote_details'] = {
                'voted_for': {
                    'username': vote.participation.user.username,
                    'video_title': vote.participation.video_submission.title,
                    'video_id': vote.participation.video_submission.id, 
                    'votes_received': vote.participation.votes_received,
                },
                'voted_at': vote.created_at
            }

        return Response(data)

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

        # Check if tournament is full - reject if it's not a repeating tournament
        if tournament.participant_limit:
            current_participants = Participation.objects.filter(tournament=tournament).count()
            
            if current_participants >= tournament.participant_limit:
                if not tournament.is_repeating:
                    return Response(
                        {"error": "Tournament has reached maximum participants"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                else:
                    # If it's repeating but full, reject with a message to try the newest group
                    parent = tournament.parent_tournament or tournament
                    newest_group = parent.child_tournaments.order_by('-created_at').first()
                    
                    if newest_group and newest_group.id != tournament.id:
                        return Response({
                            "error": "This group is full. Please join the newest group.",
                            "newest_group": {
                                "id": newest_group.id,
                                "title": newest_group.title,
                                "group": newest_group.group_name
                            }
                        }, status=status.HTTP_400_BAD_REQUEST)
                        
                    return Response(
                        {"error": "Tournament has reached maximum participants and no new groups are available"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

        try:
            with transaction.atomic():
                video_serializer = VideoSubmissionSerializer(data=request.data)
                if video_serializer.is_valid():
                    video = video_serializer.save(user=user)
                    
                    # Create participation
                    participation = Participation.objects.create(
                        user=user,
                        tournament=tournament,
                        video_submission=video
                    )
                    
                    # Deduct tickets
                    user.tickets -= tournament.entry_fee
                    user.save()
                    
                    # Check if this participation filled the tournament and it's repeating
                    if tournament.is_repeating and tournament.participant_limit:
                        # Refresh participant count from database to ensure accuracy
                        current_count = Participation.objects.filter(tournament=tournament).count()
                        
                        if current_count >= tournament.participant_limit:
                            # This was the last spot! Create a new group automatically
                            parent = tournament.parent_tournament or tournament
                            parent.create_new_group()
                    
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
        Get paginated list of tournament participants with sorting and search
        """
        tournament = self.get_object()
        participations = Participation.objects.filter(
            tournament=tournament
        ).select_related('user', 'video_submission')
        
        # Handle sorting
        sort_by = request.query_params.get('sort')
        if sort_by:
            if sort_by == 'most_votes':
                participations = participations.order_by('-votes_received')
            elif sort_by == 'most_viewed':
                participations = participations.order_by('-video_submission__views_count')
            elif sort_by == 'newest':
                participations = participations.order_by('-created_at')
            elif sort_by == 'oldest':
                participations = participations.order_by('created_at')
        else:
            # Default sorting by newest
            participations = participations.order_by('-created_at')

        # Handle search
        search = request.query_params.get('search')
        if search:
            participations = participations.filter(
                Q(video_submission__title__icontains=search) |
                Q(user__username__icontains=search) |
                Q(video_submission__description__icontains=search)
            )

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

        # Check if user is a participant in this tournament
        if not Participation.objects.filter(user=user, tournament=tournament).exists():
            return Response(
                {"error": "Only tournament participants can vote"},
                status=status.HTTP_403_FORBIDDEN
            )

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
    def vote_status(self, request, pk=None):
        """Get user's voting status for this tournament"""
        tournament = self.get_object()
        user = request.user
        
        # Check if user has voted
        vote = Vote.objects.filter(
            voter=user, 
            tournament=tournament
        ).select_related('participation__video_submission', 'participation__user').first()

        # Check if user can vote (hasn't voted yet)
        can_vote = not Vote.objects.filter(voter=user, tournament=tournament).exists()
        
        if vote:
            return Response({
                'has_voted': True,
                'can_vote': False, 
                'vote_details': {
                    'voted_for': {
                        'username': vote.participation.user.username,
                        'video_title': vote.participation.video_submission.title,
                        'video_id': vote.participation.video_submission.id, 
                        'votes_received': vote.participation.votes_received,
                    },
                    'voted_at': vote.created_at
                }
            })
        
        return Response({
            'has_voted': False,
            'can_vote': can_vote
        })

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
    
    @action(detail=False)
    def closing_soon(self, request):
        """
        Get 8 tournaments prioritized as follows:
        1. Active tournaments with participant limits that have 0 participants
        2. Active tournaments that are nearly full (90%+ capacity)
        3. Active tournaments closing soon by end_time
        4. Recently ended tournaments
        5. Any remaining tournaments if needed to fill up to 8
        """
        now = timezone.now()
        limit = 8
        result_tournaments = []

        # 1. First, get active tournaments with participant limits that have 0 participants
        empty_active_tournaments = []
        for tournament in Tournament.objects.filter(
            start_time__lte=now,
            participant_limit__isnull=False
        ).exclude(
            end_time__lte=now  # Exclude already ended tournaments
        ):
            participant_count = tournament.participations.count()
            if participant_count == 0:
                empty_active_tournaments.append(tournament)
        
        # Prioritize featured empty tournaments, then by newest start time
        empty_active_tournaments.sort(key=lambda t: (-t.featured, -t.start_time.timestamp()))
        
        # Add empty tournaments to results
        result_tournaments.extend(empty_active_tournaments[:limit])
        slots_remaining = limit - len(result_tournaments)
        
        # 2. Get nearly-full active tournaments
        if slots_remaining > 0:
            nearly_full_tournaments = []
            active_tournaments_with_limits = Tournament.objects.filter(
                start_time__lte=now,
                participant_limit__isnull=False
            ).exclude(
                id__in=[t.id for t in result_tournaments]
            ).exclude(
                end_time__lte=now  # Exclude already ended tournaments
            )
            
            for tournament in active_tournaments_with_limits:
                participant_count = tournament.participations.count()
                if tournament.participant_limit and participant_count > 0:
                    # Calculate how full the tournament is (as a percentage)
                    capacity_percentage = (participant_count / tournament.participant_limit) * 100
                    
                    # If it's over 80% full, consider it "closing soon"
                    if capacity_percentage >= 80:
                        nearly_full_tournaments.append({
                            'tournament': tournament,
                            'capacity_percentage': capacity_percentage,
                            'remaining_spots': tournament.participant_limit - participant_count
                        })
            
            # Sort by remaining spots (fewest first)
            nearly_full_tournaments.sort(key=lambda x: x['remaining_spots'])
            
            # Take only what we need to reach our limit
            for item in nearly_full_tournaments[:slots_remaining]:
                result_tournaments.append(item['tournament'])
            
            slots_remaining = limit - len(result_tournaments)
        
        # 3. Get active tournaments closing soon by end_time
        if slots_remaining > 0:
            # Look for tournaments ending within the next 48 hours
            end_threshold = now + timezone.timedelta(hours=48)
            closing_soon = list(Tournament.objects.filter(
                start_time__lte=now,
                end_time__gt=now,
                end_time__lte=end_threshold
            ).exclude(
                id__in=[t.id for t in result_tournaments]
            ).order_by('end_time')[:slots_remaining])
            
            result_tournaments.extend(closing_soon)
            slots_remaining = limit - len(result_tournaments)

        # 4. If still needed, get any active tournaments
        if slots_remaining > 0:
            any_active = list(Tournament.objects.filter(
                start_time__lte=now
            ).exclude(
                end_time__lte=now  # Exclude ended tournaments
            ).exclude(
                id__in=[t.id for t in result_tournaments]
            ).order_by('-start_time')[:slots_remaining])
            
            result_tournaments.extend(any_active)
            slots_remaining = limit - len(result_tournaments)

        # 5. If still needed, get recently ended tournaments
        if slots_remaining > 0:
            ended_tournaments = list(Tournament.objects.filter(
                end_time__lte=now
            ).exclude(
                id__in=[t.id for t in result_tournaments]
            ).order_by('-end_time')[:slots_remaining])
            
            result_tournaments.extend(ended_tournaments)
            slots_remaining = limit - len(result_tournaments)

        # Build response data
        tournaments_data = []
        for tournament in result_tournaments:
            data = TournamentListSerializer(tournament, context={'request': request}).data
            
            # Add status information
            if tournament.start_time > now:
                data['status'] = 'upcoming'
                data['time_info'] = self._get_time_until_start(tournament.start_time, now)
            elif tournament.end_time and tournament.end_time > now:
                data['status'] = 'active'
                data['time_info'] = self._get_time_until_end(tournament.end_time, now)
            elif not tournament.end_time and tournament.is_active:
                # For repeating/unlimited tournaments without end times
                data['status'] = 'active'
                
                # If it has a participant limit, show remaining spots
                if tournament.participant_limit:
                    participant_count = tournament.participations.count()
                    remaining = tournament.participant_limit - participant_count
                    if remaining == tournament.participant_limit:  # No participants yet
                        data['time_info'] = f"Be the first to join! {remaining} spots available."
                    else:
                        data['time_info'] = f"Only {remaining} spots left"
                else:
                    data['time_info'] = "Active tournament"
            else:
                data['status'] = 'ended'
                if tournament.end_time:
                    data['time_info'] = self._get_time_since_end(tournament.end_time, now)
                else:
                    data['time_info'] = "Tournament ended"
            
            # Add participation info
            data['participation_info'] = self._get_participation_info(tournament)
            
            tournaments_data.append(data)

        return Response(tournaments_data)
    def _get_time_until_start(self, start_time, now):
        """Calculate time until tournament starts"""
        time_left = start_time - now
        days = time_left.days
        hours = time_left.seconds // 3600
        minutes = (time_left.seconds % 3600) // 60
        
        if days > 0:
            return f"Starts in {days} days"
        elif hours > 0:
            return f"Starts in {hours} hours"
        else:
            return f"Starts in {minutes} minutes"

    def _get_time_until_end(self, end_time, now):
        """Calculate time until tournament ends"""
        time_left = end_time - now
        days = time_left.days
        hours = time_left.seconds // 3600
        minutes = (time_left.seconds % 3600) // 60
        
        if days > 0:
            return f"Ends in {days} days"
        elif hours > 0:
            return f"Ends in {hours} hours"
        else:
            return f"Ends in {minutes} minutes"

    def _get_time_since_end(self, end_time, now):
        """Calculate time since tournament ended"""
        time_passed = now - end_time
        days = time_passed.days
        hours = time_passed.seconds // 3600
        
        if days > 0:
            return f"Ended {days} days ago"
        elif hours > 0:
            return f"Ended {hours} hours ago"
        else:
            minutes = time_passed.seconds // 60
            return f"Ended {minutes} minutes ago"

    def _get_participation_info(self, tournament):
        """Get participation information for tournament"""
        participation_count = tournament.participations.count()
        return {
            'total_participants': participation_count,
            'limit_reached': tournament.participant_limit and participation_count >= tournament.participant_limit,
            'votes_count': tournament.votes.count()
        }

    def list(self, request, *args, **kwargs):
        """Enhanced list view with random participants for each tournament"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            tournaments_data = []
            for tournament in page:
                # Get random participants for this tournament
                participants = Participation.objects.filter(
                    tournament=tournament
                ).select_related(
                    'user',
                    'video_submission'
                )[:3]  # Limit to 3 participants
                
                # Serialize tournament data
                tournament_data = TournamentListSerializer(tournament).data
                tournament_data['category_id'] = tournament.category.id
                # Add participants data
                tournament_data['participants'] = ParticipationSerializer(
                    participants, 
                    many=True
                ).data
                
                tournaments_data.append(tournament_data)

            return self.get_paginated_response(tournaments_data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False)
    def category_view(self, request):
        """Get tournaments filtered by category with participant details"""
        category_id = request.query_params.get('category')
        if not category_id:
            return Response(
                {"error": "Category ID is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = self.filter_queryset(
            Tournament.objects.filter(category_id=category_id)
        )
        return self._get_tournaments_with_participants(queryset)

    def _get_tournaments_with_participants(self, queryset):
        """Helper method to get tournaments with participant details"""
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            tournaments_data = []
            for tournament in page:
                # Get recent participants
                participants = Participation.objects.filter(
                    tournament=tournament
                ).select_related(
                    'user',
                    'video_submission'
                ).order_by('-votes_received')[:3]
                
                tournament_data = TournamentListSerializer(tournament).data
                tournament_data['participants'] = ParticipationSerializer(
                    participants, 
                    many=True
                ).data
                
                tournaments_data.append(tournament_data)

            return self.get_paginated_response(tournaments_data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=True)
    def video_detail(self, request, pk=None):
        """Get specific video details from tournament"""
        tournament = self.get_object()
        video_id = request.query_params.get('video_id')
        
        if not video_id:
            return Response(
                {"error": "video_id parameter is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            participation = Participation.objects.get(
                tournament=tournament,
                video_submission_id=video_id
            )
        except Participation.DoesNotExist:
            return Response(
                {"error": "Video not found in this tournament"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Increment view count
        VideoSubmission.objects.filter(id=video_id).update(
            views_count=F('views_count') + 1
        )
        participation.video_submission.refresh_from_db()

        return Response({
            'tournament': {
                'id': tournament.id,
                'title': tournament.title,
                'category': tournament.category.name,
            },
            'video': {
                'id': participation.video_submission.id,
                'title': participation.video_submission.title,
                'description': participation.video_submission.description,
                'video_file': request.build_absolute_uri(participation.video_submission.video_file.url),
                'cover_image': request.build_absolute_uri(participation.video_submission.cover_image.url),
                'duration': participation.video_submission.duration,
                'views_count': participation.video_submission.views_count,
                'created_at': participation.video_submission.created_at,
            },
            'participant': {
                'username': participation.user.username,
                'avatar': request.build_absolute_uri(participation.user.avatar.url) if participation.user.avatar else None,
                'votes_received': participation.votes_received,
                'is_finalist': participation.is_finalist
            }
        })   

    @action(detail=True, methods=['post'], url_path='report-video')
    def report_video(self, request, pk=None):
        """Report a video for inappropriate content"""
        tournament = self.get_object()
        video_id = request.data.get('video_id')
        
        try:
            participation = Participation.objects.get(
                tournament=tournament,
                video_submission_id=video_id
            )
        except Participation.DoesNotExist:
            return Response(
                {"error": "Video not found in this tournament"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if user already reported this video
        if VideoReport.objects.filter(reporter=request.user, video=participation.video_submission).exists():
            return Response(
                {"error": "You have already reported this video"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = VideoReportSerializer(data=request.data)
        if serializer.is_valid():
            VideoReport.objects.create(
                video=participation.video_submission,
                reporter=request.user,
                **serializer.validated_data
            )
            return Response(
                {"message": "Video reported successfully"},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST) 

    @action(detail=False)
    def my_voted_videos(self, request):
        """Get videos the current user has voted for"""
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required"}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

        votes = Vote.objects.filter(
            voter=request.user
        ).select_related(
            'participation__video_submission',
            'participation__user',
            'tournament'
        ).order_by('-created_at')

        # Handle sorting
        sort_by = request.query_params.get('sort')
        if sort_by:
            if sort_by == 'most_votes':
                votes = votes.order_by('-participation__votes_received')
            elif sort_by == 'most_viewed':
                votes = votes.order_by('-participation__video_submission__views_count')
            elif sort_by == 'oldest':
                votes = votes.order_by('created_at')

        # Pagination
        page = self.paginate_queryset(votes)
        if page is not None:
            return self.get_paginated_response({
                'voting_stats': {
                    'total_votes_cast': votes.count(),
                    'tournaments_voted_in': votes.values('tournament').distinct().count()
                },
                'voted_videos': [{
                    'voted_at': vote.created_at,
                    'tournament': {
                        'id': vote.tournament.id,
                        'title': vote.tournament.title
                    },
                    'video': {
                        'id': vote.participation.video_submission.id,
                        'title': vote.participation.video_submission.title,
                        'description': vote.participation.video_submission.description,
                        'video_file': request.build_absolute_uri(
                            vote.participation.video_submission.video_file.url
                        ),                        
                        'cover_image': request.build_absolute_uri(
                            vote.participation.video_submission.cover_image.url
                        ),
                        'views_count': vote.participation.video_submission.views_count,
                        'votes_received': vote.participation.votes_received,
                    },
                    'participant': {
                        'username': vote.participation.user.username,
                        'avatar': request.build_absolute_uri(
                            vote.participation.user.avatar.url
                        ) if vote.participation.user.avatar else None
                    }
                } for vote in page]
            })
        
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
    

User = get_user_model()

class UserTournamentProfileViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPagination

    @action(detail=False, methods=['get'], url_path='user/(?P<username>[^/.]+)/info')
    def user_profile_info(self, request, username=None):
        """Get user info and stats only"""
        try:
            user = User.objects.get(username=username)
            participations = Participation.objects.filter(user=user)
            
            return Response({
                'user_info': {
                    'username': user.username,
                    'name': getattr(user, 'name', ''),
                    'avatar': request.build_absolute_uri(user.avatar.url) if getattr(user, 'avatar', None) else None,
                    'bio': getattr(user, 'bio', '')
                },
                'stats': {
                    'total_participations': participations.count(),
                    'total_votes_received': sum(p.votes_received for p in participations),
                    'total_views': sum(p.video_submission.views_count for p in participations),
                    'finalist_count': participations.filter(is_finalist=True).count(),
                    'tournaments_won': participations.filter(is_finalist=True).count()
                }
            })
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'], url_path='user/(?P<username>[^/.]+)/videos')
    def user_videos(self, request, username=None):
        """Get user's videos with pagination"""
        try:
            user = User.objects.get(username=username)
            participations = Participation.objects.filter(
                user=user
            ).select_related(
                'tournament',
                'video_submission'
            )

            # Handle sorting
            sort_by = request.query_params.get('sort', 'newest')
            if sort_by == 'most_votes':
                participations = participations.order_by('-votes_received')
            elif sort_by == 'most_viewed':
                participations = participations.order_by('-video_submission__views_count')
            elif sort_by == 'oldest':
                participations = participations.order_by('created_at')
            else:  # newest
                participations = participations.order_by('-created_at')

            page = self.paginate_queryset(participations)
            if page is not None:
                serializer = ParticipationSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)

        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
# Add this to lolo/tournament/api/views.py
class PublicTournamentViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet that doesn't require authentication for public tournament data"""
    authentication_classes = []  # No authentication required
    permission_classes = []      # No permissions required
    
    def get_queryset(self):
        # This method is called for all actions - always filters for showcase tournaments
        return Tournament.objects.none()  # Default empty queryset
    
    @action(detail=False, methods=['get'])
    def showcase(self, request):
        """
        Public API endpoint for showcasing tournaments
        """
        now = timezone.now()
        
        # Get active, showcase tournaments
        showcase_tournaments = Tournament.objects.filter(
            is_showcase=True,
            start_time__lte=now
        ).exclude(
            end_time__lte=now  # Exclude ended tournaments
        ).order_by('-featured', '-start_time')[:10]
        
        # Filter for truly active tournaments
        active_showcase_tournaments = []
        for tournament in showcase_tournaments:
            if tournament.is_active:  # Use the is_active property to check
                active_showcase_tournaments.append(tournament)
        
        # Custom limited serialization for public view
        result = []
        for tournament in active_showcase_tournaments:
            participant_count = tournament.participations.count()
            
            result.append({
                'id': tournament.id,
                'title': tournament.title,
                'description': tournament.description,
                'rules': tournament.rules,
                'prizes': tournament.prizes,
                'image': request.build_absolute_uri(tournament.image.url) if tournament.image else None,
                'category': tournament.category.name,
                'participant_count': participant_count,
                'participant_limit': tournament.participant_limit,
                'is_active': True,  # We've already confirmed these are active
                'featured': tournament.featured,
                'start_time': tournament.start_time
            })
        
        return Response(result)
    
class SponsorViewSet(viewsets.ModelViewSet):
    queryset = Sponsor.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        django_filters.DjangoFilterBackend,
        filters.SearchFilter
    ]
    search_fields = ['name', 'description']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return SponsorDetailSerializer
        return SponsorSerializer
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action == 'public':
            return []  # No permissions required for public action
        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['get'])
    def public(self, request):
        """Public API endpoint for active sponsors"""
        sponsors = Sponsor.objects.filter(is_active=True)
        
        result = []
        for sponsor in sponsors:
            result.append({
                'id': sponsor.id,
                'name': sponsor.name,
                'description': sponsor.description,
                'logo': request.build_absolute_uri(sponsor.logo.url) if sponsor.logo else None,
                'website_url': sponsor.website_url
            })
        
        return Response(result)