from django.contrib import admin
from django.utils.html import format_html
from django.conf import settings

from .models import *

admin.site.register(Downloader)
admin.site.register(MedcatModel)


class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('key_short', 'identifier', 'created_at', 'expires_at', 'is_active', 'is_expired')
    list_filter = ('is_active', 'created_at', 'expires_at')
    search_fields = ('key', 'identifier')

    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing object
            return ('key', 'created_at', 'api_key_link', 'expires_at')
        else:  # Creating a new object
            return ('key', 'created_at', 'api_key_link')

    def key_short(self, obj):
        return f"{obj.key[:10]}..."
    key_short.short_description = 'API Key'

    def is_expired(self, obj):
        from django.utils import timezone
        return obj.expires_at < timezone.now()
    is_expired.boolean = True
    is_expired.short_description = 'Expired'

    def api_key_link(self, obj: APIKey):
        if bool(obj.key) and obj.is_active:
            current_site = settings.BASE_URL
            base_url = f"{current_site}/manual-api-callback/"
            callback_url = f"{base_url}?api_key={obj.key}"
            unique_id = obj.identifier

            formatted = format_html(
                '<div style="margin: 10px 0;">'
                '<input type="text" value="{}" id="api-url-{}" readonly '
                'style="width: 500px; padding: 5px; margin-right: 10px;" /> '
                '<button type="button" onclick="'
                'navigator.clipboard.writeText(\'{}\').then(function() {{'
                '  document.getElementById(\'copy-status-{}\').textContent = \'✓ Copied!\';'
                '  setTimeout(function() {{'
                '    document.getElementById(\'copy-status-{}\').textContent = \'\';'
                '  }}, 2000);'
                '}});'
                '" style="padding: 5px 10px; cursor: pointer;">Copy URL</button>'
                '<span id="copy-status-{}" style="margin-left: 10px; color: green;"></span>'
                '</div>',
                callback_url, unique_id, callback_url, unique_id, unique_id, unique_id
            )
            return formatted
        return "-"
    api_key_link.short_description = 'API Key URL'


# Register your models here.
admin.site.register(APIKey, APIKeyAdmin)
