from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('api/bot', include('bot.urls')),
]

if settings.ADMIN_ENABLED:
    urlpatterns.insert(0, path('admin/', admin.site.urls))
