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

    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing object
            return ('key', 'created_at', 'expires_at')
        else:  # Creating a new object
            return ('key', 'created_at')

    def key_short(self, obj):
        return f"{obj.key[:10]}..."
    key_short.short_description = 'API Key'

    def is_expired(self, obj):
        from django.utils import timezone
        return obj.expires_at < timezone.now()
    is_expired.boolean = True
    is_expired.short_description = 'Expired'

    def api_key_link(self, obj):
        if obj.key and obj.is_active:
            callback_url = f"/manual-api-callback/?api_key={self.key}"
            unique_id = self.identifier

            return format_html(
                '<div style="margin: 10px 0;">'
                '<input type="text" value="{}" readonly '
                'style="width: 500px; padding: 5px; margin-right: 10px;" /> '
                '<button type="button" onclick="copyToClipboard(\'{}\', \'{}\')" '
                'style="padding: 5px 10px; cursor: pointer;">Copy URL</button>'
                '<span id="copy-status-{}" style="margin-left: 10px; color: green;"></span>'
                '</div>'
                '<script>'
                'function copyToClipboard(text, id) {{'
                '  navigator.clipboard.writeText(text).then(function() {{'
                '    document.getElementById("copy-status-" + id).textContent = "✓ Copied!";'
                '    setTimeout(function() {{'
                '      document.getElementById("copy-status-" + id).textContent = "";'
                '    }}, 2000);'
                '}}'
                '</script>',
                callback_url,    # 1st {} - input value
                callback_url,    # 2nd {} - text to copy
                unique_id,   # 3rd {} - ID for JavaScript function
                unique_id    # 4th {} - ID for status span
            )
        return "-"
    api_key_link.short_description = 'API Key URL'


# Register your models here.
admin.site.register(UploadedText, UploadedTextAdmin)
admin.site.register(APIKey, APIKeyAdmin)
