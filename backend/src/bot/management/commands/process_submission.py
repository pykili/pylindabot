from django.core.management.base import BaseCommand

from bot.logic import processing


class Command(BaseCommand):
    help = 'Process submission by ID'

    def add_arguments(self, parser):
        parser.add_argument('submission_id', type=int)

    def handle(self, *args, **options):
        submission_id = options['submission_id']
        processing.start_processing(submission_id)
