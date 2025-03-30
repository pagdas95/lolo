# lolo/tournament/models.py
from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator

class Category(models.Model):
    """Tournament categories (e.g., Gaming, Music, Sports)"""
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Name of the category"
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed description of the category"
    )
    
    class Meta:
        verbose_name_plural = "Categories"
    
    def __str__(self):
        return self.name

# lolo/tournament/models.py

class Tournament(models.Model):
    """
    Main tournament model with rules and prizes as text fields
    """
    title = models.CharField(
        max_length=200,
        help_text="Tournament title"
    )
    description = models.TextField(
        help_text="Tournament description"
    )
    rules = models.TextField(
        help_text="Detailed tournament rules and guidelines",
        blank=True  # Making it optional
    )
    prizes = models.TextField(
        help_text="Tournament prizes and rewards",
        blank=True  # Making it optional
    )
    image = models.ImageField(
        upload_to='tournament_images/',
        help_text="Tournament cover image"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='tournaments'
    )

    featured = models.BooleanField(
        default=False,
        help_text="Featured tournaments will be highlighted"
    )
    
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Optional for repeating tournaments that end when filled"
    )
    participant_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of participants (null for unlimited)"
    )

    is_showcase = models.BooleanField(
    default=False,
    help_text="Show this tournament in public showcase carousels"
    )
    # New fields for repeating tournaments
    is_repeating = models.BooleanField(
        default=False,
        help_text="If true, new groups will be created when this tournament fills up"
    )
    parent_tournament = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='child_tournaments',
        help_text="Parent tournament for generated groups"
    )
    group_name = models.CharField(
        max_length=20,
        blank=True,
        help_text="Group identifier (e.g., 'A', 'B', 'C')"
    )
    active_group_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of active groups created from this tournament"
    )
    # Existing fields
    finalists_count = models.PositiveIntegerField(
        default=3,
        help_text="Number of finalists to be selected"
    )
    entry_fee = models.PositiveIntegerField(
        default=1,
        help_text="Number of tickets required to enter"
    )
    is_final_tournament = models.BooleanField(
        default=False,
        help_text="Indicates if this is a final tournament"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_tournaments'
    )
    views_count = models.PositiveIntegerField(default=0)


    def __str__(self):
        if self.group_name:
            return f"{self.title} - Group {self.group_name}"
        return self.title

    @property
    def is_active(self):
        from django.utils import timezone
        now = timezone.now()
        
        # For repeating tournaments with no end_time
        if self.is_repeating and not self.end_time:
            # Check if tournament has started and is not full
            if self.start_time <= now:
                if self.participant_limit:
                    participant_count = self.participations.count()
                    return participant_count < self.participant_limit
                return True  # No participant limit, always active after start
            return False  # Not started yet
        
        # For normal tournaments with end_time
        return self.start_time <= now <= self.end_time
    
    def create_new_group(self):
        """Create a new tournament group when this one fills up"""
        if not self.is_repeating:
            return None
            
        # For parent tournaments
        if not self.parent_tournament:
            # Generate next group letter (A, B, C, etc.)
            next_group = chr(ord('A') + self.active_group_count)
            from django.utils import timezone
            current_time = timezone.now()
            # Create new tournament with same settings
            new_tournament = Tournament.objects.create(
                title=self.title,
                description=self.description,
                rules=self.rules,
                prizes=self.prizes,
                image=self.image,
                category=self.category,
                featured=self.featured,
                is_showcase=self.is_showcase,
                start_time=current_time,
                end_time=self.end_time,
                participant_limit=self.participant_limit,
                finalists_count=self.finalists_count,
                entry_fee=self.entry_fee,
                is_final_tournament=self.is_final_tournament,
                created_by=self.created_by,
                # New fields
                is_repeating=True,
                parent_tournament=self,
                group_name=next_group
            )
            
            # Update the parent tournament
            self.active_group_count += 1
            self.save(update_fields=['active_group_count'])
            
            return new_tournament
            
        # Don't allow child tournaments to create new groups
        return None

class VideoSubmission(models.Model):
    """Video entries for tournaments"""
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    views_count = models.PositiveIntegerField(default=0)
    video_file = models.FileField(
        upload_to='tournament_videos/',
        validators=[FileExtensionValidator(allowed_extensions=['mp4', 'mov', 'avi'])]
    )
    cover_image = models.ImageField(
        upload_to='video_covers/',
        help_text="Thumbnail for the video"
    )
    duration = models.DurationField(
        null=True,
        blank=True,
        help_text="Video duration (automatically calculated)"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='video_submissions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(
        default=False,
        help_text="Indicates if the video has been processed"
    )

    def __str__(self):
        return self.title

class Participation(models.Model):
    """Tournament participation records"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='participations'
    )
    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name='participations'
    )
    video_submission = models.OneToOneField(
        VideoSubmission,
        on_delete=models.CASCADE,
        related_name='tournament_participation'
    )
    votes_received = models.PositiveIntegerField(default=0)
    is_finalist = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'tournament']
        verbose_name_plural = "Participations"

    def __str__(self):
        return f"{self.user.username} - {self.tournament.title}"

class Vote(models.Model):
    """User votes for tournament entries"""
    voter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='votes_cast'
    )
    participation = models.ForeignKey(
        Participation,
        on_delete=models.CASCADE,
        related_name='votes'
    )
    tournament = models.ForeignKey(  # Add this field
        'Tournament',
        on_delete=models.CASCADE,
        related_name='votes'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['voter', 'tournament']  # Fixed unique_together
        verbose_name_plural = "Votes"

    def __str__(self):
        return f"{self.voter.username} voted for {self.participation}"

    def save(self, *args, **kwargs):
        # Automatically set the tournament from the participation
        if not self.tournament_id and self.participation:
            self.tournament = self.participation.tournament
        super().save(*args, **kwargs)

class VideoReport(models.Model):
    """Reports for inappropriate videos"""
    REPORT_REASONS = [
        ('inappropriate_username', 'Inappropriate username'),
        ('stolen_content', 'Stolen content'),
        ('adult_content', 'Nudity/Adult content'),
        ('racist', 'Racist'),
        ('promoting_products', 'Promoting products'),
        ('other', 'Other'),
    ]

    video = models.ForeignKey(
        VideoSubmission,
        on_delete=models.CASCADE,
        related_name='reports'
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='video_reports'
    )
    reason = models.CharField(
        max_length=50,
        choices=REPORT_REASONS
    )
    details = models.TextField(
        help_text="Additional details about the report"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)

    class Meta:
        unique_together = ['reporter', 'video']  # One report per video per user

    def __str__(self):
        return f"Report by {self.reporter.username} on {self.video.title}"