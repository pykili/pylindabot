from django.contrib import admin

from bot import models


class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'seq', 'group', 'name', 'type', 'is_enabled')
    ordering = ('group', 'seq')


class GroupsAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    ordering = ('id',)


class SubmissionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'status',
        'author',
        'assignment_name',
        'task_id',
        'pull_url',
    )


class BotUserAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'full_name',
        'groups_names',
        'telegram_chat_id',
        'github_login',
    )


admin.site.register(models.Groups, GroupsAdmin)
admin.site.register(models.Assignment, AssignmentAdmin)
admin.site.register(models.Submission, SubmissionAdmin)
admin.site.register(models.BotUser, BotUserAdmin)
admin.site.register(models.GithubRepository)
admin.site.register(models.AssignmentGistCache)
admin.site.register(models.SubmissionEvent)
