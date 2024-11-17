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
    end_time = models.DateTimeField()
    participant_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of participants (null for unlimited)"
    )
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
        return self.title

    @property
    def is_active(self):
        from django.utils import timezone
        now = timezone.now()
        return self.start_time <= now <= self.end_time

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