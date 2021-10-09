from django.core.management.base import BaseCommand

from bot import models


class Command(BaseCommand):
    help = 'Add a new group polling with telegram bot'

    def add_arguments(self, parser):
        parser.add_argument('group_name', type=str, required=True)
        parser.add_argument('group_id', type=int, required=True)
    
    def handle(self, *args, **options):
        group = models.Groups.objects.create(id=options['group_id'], name=options['group_name'])
        group.save()
        self.stdout.write(self.style.SUCCESS(f'{group} created'))
 
