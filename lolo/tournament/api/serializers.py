# lolo/tournament/api/serializers.py
from rest_framework import serializers
from ..models import Category, Tournament, VideoSubmission, Participation, Vote, VideoReport, Sponsor

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']

class TournamentListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_id = serializers.IntegerField(source='category.id', read_only=True) 
    participant_count = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)
    status = serializers.CharField(read_only=True, required=False)
    time_info = serializers.CharField(read_only=True, required=False)
    participation_info = serializers.DictField(read_only=True, required=False)
    group_info = serializers.SerializerMethodField()

    class Meta:
        model = Tournament
        fields = [
            'id', 
            'title', 
            'image', 
            'category_name',
            'category_id',
            'start_time', 
            'end_time', 
            'participant_count',
            'is_active', 
            'entry_fee',
            'prizes',
            'rules',
            'status',
            'time_info',
            'participation_info',
            'is_repeating',
            'group_name',
            'group_info',
            'participant_limit'
        ]

    def get_participant_count(self, obj):
        return obj.participations.count()
        
    def get_group_info(self, obj):
        if not obj.is_repeating:
            return None
            
        if obj.parent_tournament:
            return {
                'is_child': True,
                'parent_id': obj.parent_tournament.id,
                'parent_title': obj.parent_tournament.title,
                'group': obj.group_name
            }
        else:
            # This is a parent tournament
            group_count = obj.active_group_count
            child_tournaments = obj.child_tournaments.all()
            
            return {
                'is_parent': True,
                'active_groups': group_count,
                'child_tournaments': [
                    {
                        'id': child.id,
                        'title': child.title,
                        'group': child.group_name,
                        'participants': child.participations.count(),
                        'is_full': child.participations.count() >= child.participant_limit if child.participant_limit else False
                    } for child in child_tournaments
                ]
            }

class TournamentDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    group_info = serializers.SerializerMethodField()

    class Meta:
        model = Tournament
        fields = [
            'id',
            'title',
            'description',
            'rules',
            'prizes',
            'image',
            'category',
            'category_name',
            'start_time',
            'end_time',
            'participant_limit',
            'finalists_count',
            'entry_fee',
            'is_final_tournament',
            'is_active',
            'featured',
            'created_at',
            'updated_at',
            'created_by',
            'is_repeating',
            'parent_tournament',
            'group_name',
            'group_info'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']
        
    def get_group_info(self, obj):
        if not obj.is_repeating:
            return None
            
        if obj.parent_tournament:
            return {
                'is_child': True,
                'parent_id': obj.parent_tournament.id,
                'parent_title': obj.parent_tournament.title,
                'group': obj.group_name
            }
        else:
            # This is a parent tournament
            group_count = obj.active_group_count
            child_tournaments = obj.child_tournaments.all()
            
            return {
                'is_parent': True,
                'active_groups': group_count,
                'child_tournaments': [
                    {
                        'id': child.id,
                        'title': child.title,
                        'group': child.group_name,
                        'participants': child.participations.count(),
                        'is_full': child.participations.count() >= child.participant_limit if child.participant_limit else False
                    } for child in child_tournaments
                ]
            }

class VideoSubmissionSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = VideoSubmission
        fields = [
            'id', 'title', 'description', 'video_file',
            'cover_image', 'duration', 'user_username',
            'created_at', 'processed'
        ]
        read_only_fields = ['duration', 'processed', 'user_username']

class ParticipationSerializer(serializers.ModelSerializer):
    video = VideoSubmissionSerializer(source='video_submission')
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_avatar = serializers.SerializerMethodField()

    class Meta:
        model = Participation
        fields = [
            'id', 'user_username', 'user_avatar',  'tournament', 'video',
            'votes_received', 'is_finalist', 'created_at'
        ]
        read_only_fields = ['votes_received', 'is_finalist']

    def get_user_avatar(self, obj):
        request = self.context.get('request')
        if obj.user.avatar:
            return request.build_absolute_uri(obj.user.avatar.url) if request else obj.user.avatar.url
        return None

class VoteSerializer(serializers.ModelSerializer):
    voter_username = serializers.CharField(source='voter.username', read_only=True)
    participation_details = serializers.SerializerMethodField()

    class Meta:
        model = Vote
        fields = ['id', 'voter_username', 'participation_details', 'created_at']
        read_only_fields = ['voter_username']

    def get_participation_details(self, obj):
        return {
            'tournament': obj.participation.tournament.title,
            'video_title': obj.participation.video_submission.title
        }

class VideoReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoReport
        fields = ['reason', 'details']

class SponsorSerializer(serializers.ModelSerializer):
    tournament_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Sponsor
        fields = [
            'id', 'name', 'description', 'logo', 'website_url', 
            'is_active', 'tournament_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_tournament_count(self, obj):
        return obj.tournaments.count()

class SponsorDetailSerializer(serializers.ModelSerializer):
    tournaments = serializers.SerializerMethodField()
    
    class Meta:
        model = Sponsor
        fields = [
            'id', 'name', 'description', 'logo', 'website_url', 
            'is_active', 'tournaments', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_tournaments(self, obj):
        return [{
            'id': t.id,
            'title': t.title,
            'image': self.context['request'].build_absolute_uri(t.image.url) if t.image else None
        } for t in obj.tournaments.all()]