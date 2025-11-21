import secrets

from datetime import timedelta

from django.db import models
from django.core.files.storage import FileSystemStorage
from django.utils import timezone


MODEL_FS = FileSystemStorage(location="/medcat_data")


cooldown_minutes = 30


# Create your models here.
class UploadedText(models.Model):
    text = models.TextField(default="", blank=True)
    create_time = models.DateTimeField(auto_now_add=True)


class Downloader(models.Model):
    first_name = models.CharField(max_length=20)
    last_name = models.CharField(max_length=20)
    email = models.EmailField(max_length=50)
    affiliation = models.CharField(max_length=100)
    funder = models.CharField(max_length=100, blank=True, default="")
    use_case = models.TextField(max_length=200)
    downloaded_file = models.CharField(max_length=100)

    def __str__(self):
        return f'{self.first_name} - {self.last_name}'


class MedcatModel(models.Model):
    model_name = models.CharField(max_length=20, unique=True)
    model_file = models.FileField(storage=MODEL_FS)
    model_display_name = models.CharField(max_length=50)
    model_description = models.TextField(max_length=200)


class Question(models.Model):
    """Multiple choice questions for the questionnaire"""
    question_text = models.TextField()
    option_a = models.CharField(max_length=255)
    option_b = models.CharField(max_length=255)
    option_c = models.CharField(max_length=255)
    option_d = models.CharField(max_length=255)
    correct_answer = models.CharField(
        max_length=1,
        choices=[('a', 'A'), ('b', 'B'), ('c', 'C'), ('d', 'D')]
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.question_text[:50]


class UserAttempt(models.Model):
    """Track user attempts to prevent brute-forcing"""
    identifier = models.CharField(max_length=255, db_index=True)  # IP or user ID
    attempted_at = models.DateTimeField(auto_now_add=True)
    passed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-attempted_at']

    @classmethod
    def can_attempt(cls, identifier):
        """Check if user can attempt the questionnaire"""
        thirty_mins_ago = timezone.now() - timedelta(minutes=cooldown_minutes)
        recent_failed = cls.objects.filter(
            identifier=identifier,
            attempted_at__gte=thirty_mins_ago,
            passed=False
        ).exists()
        return not recent_failed

    @classmethod
    def get_cooldown_remaining(cls, identifier):
        """Get remaining cooldown time in seconds"""
        thirty_mins_ago = timezone.now() - timedelta(minutes=cooldown_minutes)
        recent_failed = cls.objects.filter(
            identifier=identifier,
            attempted_at__gte=thirty_mins_ago,
            passed=False
        ).first()

        if recent_failed:
            time_passed = timezone.now() - recent_failed.attempted_at
            remaining = timedelta(minutes=cooldown_minutes) - time_passed
            return max(0, int(remaining.total_seconds()))
        return 0


class APIKey(models.Model):
    """Temporary API keys for successful completions"""
    key = models.CharField(max_length=64, unique=True, db_index=True)
    identifier = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = secrets.token_urlsafe(48)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=cooldown_minutes)
        super().save(*args, **kwargs)

    @classmethod
    def is_valid(cls, key):
        """Check if an API key is valid and not expired"""
        try:
            api_key = cls.objects.get(key=key, is_active=True)
            if api_key.expires_at > timezone.now():
                return True
            else:
                # Mark as inactive if expired
                api_key.is_active = False
                api_key.save()
                return False
        except cls.DoesNotExist:
            return False

    def __str__(self):
        return f"{self.key[:10]}... (expires: {self.expires_at})"
