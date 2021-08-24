from django.urls import path

from bot.api import views

urlpatterns = [
    path('/telegram', views.TelegramHookView.as_view()),
    path('/github', views.GithubHookView.as_view()),
]
