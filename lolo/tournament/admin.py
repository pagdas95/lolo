# lolo/tournament/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Category, Tournament, VideoSubmission, Participation, Vote, VideoReport



class ParticipationInline(admin.TabularInline):
    model = Participation
    extra = 0
    readonly_fields = ['votes_received', 'created_at']
    can_delete = False
    show_change_link = True

class VoteInline(admin.TabularInline):
    model = Vote
    extra = 0
    readonly_fields = ['created_at']
    can_delete = False

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'tournament_count']
    search_fields = ['name']
    
    def tournament_count(self, obj):
        return obj.tournaments.count()
    tournament_count.short_description = 'Number of Tournaments'

@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = [
        'title', 
        'category', 
        'start_time', 
        'end_time', 
        'participant_count',
        'is_active',
        'view_participants',
        'featured',
    ]
    actions = ['select_finalists', 'close_tournament']
    inlines = [ParticipationInline]
    list_filter = ['category', 'is_final_tournament', 'featured', ('start_time', admin.DateFieldListFilter)]
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = [
        (None, {
            'fields': ['title', 'description','rules', 'prizes', 'image', 'featured']
        }),
        ('Category & Settings', {
            'fields': ['category', 'participant_limit', 'finalists_count', 'is_final_tournament']
        }),
        ('Timing', {
            'fields': ['start_time', 'end_time']
        }),
        ('Metadata', {
            'fields': ['created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]

    def participant_count(self, obj):
        count = obj.participations.count()
        return format_html(
            '<a href="{}?tournament__id__exact={}">{} participants</a>',
            reverse('admin:tournament_participation_changelist'),
            obj.id,
            count
        )
    participant_count.short_description = 'Participants'

    def view_participants(self, obj):
        url = reverse('admin:tournament_participation_changelist')
        return format_html(
            '<a class="button" href="{}?tournament__id__exact={}">View Participants</a>',
            url,
            obj.id
        )
    view_participants.short_description = 'Participants'

    def is_active(self, obj):
        return obj.is_active
    is_active.boolean = True
    is_active.short_description = 'Active'


    def select_finalists(self, request, queryset):
        for tournament in queryset:
            # Select top participants based on votes
            top_participants = tournament.participations.order_by(
                '-votes_received'
            )[:tournament.finalists_count]
            
            # Mark them as finalists
            for participation in top_participants:
                participation.is_finalist = True
                participation.save()
                
        self.message_user(request, f"Selected finalists for {queryset.count()} tournaments")
    select_finalists.short_description = "Select finalists for selected tournaments"

    def close_tournament(self, request, queryset):
        from django.utils import timezone
        queryset.update(end_time=timezone.now())
        self.message_user(request, f"Closed {queryset.count()} tournaments")
    close_tournament.short_description = "Close selected tournaments"


@admin.register(VideoSubmission)
class VideoSubmissionAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'user',
        'upload_date',
        'duration',
        'processed',
        'preview_video'
    ]

    actions = ['mark_as_processed', 'mark_as_unprocessed']
    inlines = [ParticipationInline]
    list_filter = ['processed', 'created_at', 'user']
    search_fields = ['title', 'description', 'user__username']
    readonly_fields = ['duration', 'processed', 'created_at']
    
    def preview_video(self, obj):
        if obj.cover_image:
            return format_html(
                '<img src="{}" style="max-height: 50px;"/>',
                obj.cover_image.url
            )
        return "No preview"
    preview_video.short_description = 'Preview'

    def upload_date(self, obj):
        return obj.created_at.strftime('%Y-%m-%d %H:%M')
    upload_date.short_description = 'Uploaded'

@admin.register(Participation)
class ParticipationAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'tournament',
        'video_title',
        'votes_received',
        'is_finalist',
        'created_at'
    ]
    list_filter = ['tournament', 'is_finalist', 'created_at']
    search_fields = ['user__username', 'tournament__title', 'video_submission__title']
    readonly_fields = ['votes_received', 'created_at']
    
    def video_title(self, obj):
        return obj.video_submission.title
    video_title.short_description = 'Video'

    def mark_as_processed(self, request, queryset):
        queryset.update(processed=True)
        self.message_user(request, f"Marked {queryset.count()} videos as processed")
    mark_as_processed.short_description = "Mark selected videos as processed"

    def mark_as_unprocessed(self, request, queryset):
        queryset.update(processed=False)
        self.message_user(request, f"Marked {queryset.count()} videos as unprocessed")
    mark_as_unprocessed.short_description = "Mark selected videos as unprocessed"

@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ['voter', 'get_video', 'tournament', 'created_at']
    list_filter = ['tournament', 'created_at']
    search_fields = [
        'voter__username',
        'participation__user__username',
        'participation__video_submission__title'
    ]
    readonly_fields = ['created_at']

    def get_video(self, obj):
        return obj.participation.video_submission.title
    get_video.short_description = 'Voted For'

@admin.register(VideoReport)
class VideoReportAdmin(admin.ModelAdmin):
    list_display = ['video', 'reporter', 'reason', 'created_at', 'resolved', 'view_video']
    list_filter = ['reason', 'resolved', 'created_at']
    search_fields = ['video__title', 'reporter__username', 'details']
    date_hierarchy = 'created_at'

    def view_video(self, obj):
        url = reverse('admin:tournament_videosubmission_change', args=[obj.video.id])
        return format_html(
            '<a class="button" href="{}">View Video</a>',
            url
        )
    view_video.short_description = 'Video Details'

    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing existing object
            return ['video', 'reporter', 'reason', 'created_at']
        return ['created_at']

# Optional: Customize admin site header and title
admin.site.site_header = 'Tournament Management'
admin.site.site_title = 'Tournament Admin'
admin.site.index_title = 'Tournament Administration'

