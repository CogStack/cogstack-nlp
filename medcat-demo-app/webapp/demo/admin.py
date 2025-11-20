from django.contrib import admin
from .models import *

admin.site.register(Downloader)
admin.site.register(MedcatModel)

def remove_text(modeladmin, request, queryset):
    UploadedText.objects.all().delete()

class UploadedTextAdmin(admin.ModelAdmin):
    model = UploadedText
    actions = [remove_text]

# Register your models here.
admin.site.register(UploadedText, UploadedTextAdmin)

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('question_text_short', 'correct_answer', 'is_active')
    list_filter = ('is_active', 'correct_answer')
    search_fields = ('question_text',)

    def question_text_short(self, obj):
        return obj.question_text[:50] + '...' if len(obj.question_text) > 50 else obj.question_text
    question_text_short.short_description = 'Question'


@admin.register(UserAttempt)
class UserAttemptAdmin(admin.ModelAdmin):
    list_display = ('identifier', 'attempted_at', 'passed')
    list_filter = ('passed', 'attempted_at')
    search_fields = ('identifier',)
    readonly_fields = ('identifier', 'attempted_at', 'passed')

    def has_add_permission(self, request):
        return False


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('key_short', 'identifier', 'created_at', 'expires_at', 'is_active', 'is_expired')
    list_filter = ('is_active', 'created_at', 'expires_at')
    search_fields = ('key', 'identifier')
    readonly_fields = ('key', 'created_at', 'expires_at')

    def key_short(self, obj):
        return f"{obj.key[:10]}..."
    key_short.short_description = 'API Key'

    def is_expired(self, obj):
        from django.utils import timezone
        return obj.expires_at < timezone.now()
    is_expired.boolean = True
    is_expired.short_description = 'Expired'

    def has_add_permission(self, request):
        return False
