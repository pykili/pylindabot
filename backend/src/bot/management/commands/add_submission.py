from django.core.management.base import BaseCommand
from django.db import utils

from bot import models
from bot.logic import processing


class Command(BaseCommand):
    help = 'Start polling with telegram bot'

    def add_arguments(self, parser):
        parser.add_argument('--telegram-chat-id', type=int, required=True)
        parser.add_argument('--assignment-id', type=int, required=True)
        parser.add_argument('--task-id', type=int, required=True)
        parser.add_argument('--accepted', action='store_true')
        parser.add_argument('--objectkey', type=str, required=True)
        parser.add_argument('--assignment-gist-url', type=str, required=True)
        parser.add_argument('--submission-gist-url', type=str, required=True)

    def handle(self, *args, **options):
        user = models.BotUser.objects.filter(
            telegram_chat_id=options['telegram_chat_id']
        ).first()

        if user is None:
            self.stdout.write(
                self.style.ERROR(
                    f'No user with telegram-chat-id: '
                    f'{options["telegram_chat_id"]}'
                )
            )
            return

        if user.github_login is None:
            self.stdout.write(self.style.ERROR(f'{user} has no github login'))
            return

        try:
            submission = models.Submission.objects.create(
                assignment_type=models.AssignmentType.Homework.value,
                assignment_id=options['assignment_id'],
                task_id=options['task_id'],
                author=user,
                status=models.SubmissionStatus.Pending.value,
                objectkey=options['objectkey'],
                gist_url=options['assignment_gist_url'],
            )
        except utils.IntegrityError:
            submission = models.Submission.objects.get(
                assignment_type=models.AssignmentType.Homework.value,
                assignment_id=options['assignment_id'],
                task_id=options['task_id'],
                author=user,
            )
            self.stdout.write(self.style.ERROR(f'{submission} already exists'))
            return

        self.stdout.write(self.style.SUCCESS(f'{submission} created'))

        self.stdout.write(self.style.WARNING('Start processing file...'))

        processing.start_processing(submission.id, notify=False)

        submission = models.Submission.objects.get(id=submission.id)

        self.stdout.write(self.style.SUCCESS('Submission processed'))

        if options['accepted']:
            self.stdout.write(self.style.WARNING('Setting accepted status'))
            submission.status = models.SubmissionStatus.Accepted.value
            submission.save()

        submission.create_event(
            'migrated',
            payload={'submission_gist_url': options['submission_gist_url']},
        )

        self.stdout.write(self.style.SUCCESS('DONE'))
