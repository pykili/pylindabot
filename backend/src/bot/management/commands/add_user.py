from django.core.management.base import BaseCommand

from bot import models


class Command(BaseCommand):
    help = 'Start polling with telegram bot'

    def add_arguments(self, parser):
        parser.add_argument(
            'role', type=str, choices=[r.value for r in models.BotUserRole]
        )
        parser.add_argument('first_name', type=str)
        parser.add_argument('last_name', type=str)
        parser.add_argument('--groups', type=int, nargs='+', required=True)
        parser.add_argument('--telegram_login', type=str)
        parser.add_argument('--telegram_chat_id', type=str)
        parser.add_argument('--github_login', type=str)

    def handle(self, *args, **options):
        kwargs = {
            'role': options['role'],
            'first_name': options['first_name'],
            'last_name': options['last_name'],
            'telegram_login': options.get('telegram_login'),
            'telegram_chat_id': options.get('telegram_chat_id'),
            'github_login': options.get('github_login'),
        }
        groups_ids = options['groups']

        if kwargs['role'] in models.STAFF_ROLES:
            assert (
                kwargs['telegram_login'] is not None
                and kwargs['telegram_chat_id'] is not None
                and kwargs['github_login'] is not None
            ), 'Not all fields specified for role'

        groups = list(models.Groups.objects.filter(id__in=groups_ids))

        assert len(groups) == len(groups_ids), 'Can not find some groups'

        user = models.BotUser.objects.create(**kwargs)

        for group in groups:
            group.users.add(user)
            group.save()

        self.stdout.write(self.style.SUCCESS(f'{user} created'))
