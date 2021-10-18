from django.core.management.base import BaseCommand

from bot import models


class Command(BaseCommand):
    help = 'Add a new group polling with telegram bot'

    def add_arguments(self, parser):
        parser.add_argument('group_name', type=str)
        parser.add_argument('group_id', type=int)
    
    def handle(self, *args, **options):
        assert "group_id" in options and "group_name" in options, "both group_id and group_name arguments should be provided"
        group = models.Groups.objects.create(id=options['group_id'], name=options['group_name'])
        group.save()
        self.stdout.write(self.style.SUCCESS(f'{group} created'))
 
