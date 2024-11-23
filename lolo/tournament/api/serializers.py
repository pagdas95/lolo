# lolo/tournament/api/serializers.py
from rest_framework import serializers
from ..models import Category, Tournament, VideoSubmission, Participation, Vote

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
            'prizes',  # Now a text field
            'rules',    # Added rules to list view
            'status',
            'time_info',
            'participation_info'
        ]

    def get_participant_count(self, obj):
        return obj.participations.count()

class TournamentDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    is_active = serializers.BooleanField(read_only=True)

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
            'created_by'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

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