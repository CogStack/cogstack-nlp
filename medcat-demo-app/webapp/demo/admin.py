from django.contrib import admin
from .models import *

admin.site.register(Downloader)
admin.site.register(MedcatModel)

def remove_text(modeladmin, request, queryset):
    UploadedText.objects.all().delete()


class UploadedTextAdmin(admin.ModelAdmin):
    model = UploadedText
    actions = [remove_text]


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


# Register your models here.
admin.site.register(UploadedText, UploadedTextAdmin)
admin.site.register(APIKey, APIKeyAdmin)
