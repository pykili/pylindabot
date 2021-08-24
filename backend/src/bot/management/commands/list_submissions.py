import collections

from django.core.management.base import BaseCommand
from django.utils import timezone

from bot import models


class Command(BaseCommand):
    help = 'List submissions'

    def add_arguments(self, parser):
        parser.add_argument('--groups', nargs='+', type=int)

    def handle(self, *args, **options):
        kwrags = {}

        if options['groups']:
            kwrags['author__groups__in'] = options['groups']

        cols = [
            'id',
            'real_assignment__type',
            'real_assignment__name',
            'task_id',
            'status',
            'pull_url',
            'author__id',
        ]

        headers = [
            'submission_id',
            'assignment_type',
            'assignment_name',
            'task_id',
            'status',
            'pull_url',
            'submission_author',
            'accepted_at',
            'accepted_by',
        ]

        rows = models.Submission.objects.filter(**kwrags).values(*cols)
        events = self._get_events(rows)
        all_users = self._get_users()

        print(*headers, sep='\t')

        for row in rows:
            items = []
            for col in cols:
                item = row[col]
                if col in ['author__id']:
                    item = all_users[row[col]].full_name
                items.append(item)
            submission_events = events.get(row['id'], [])
            if (
                submission_events
                and row['status'] == models.SubmissionStatus.Accepted.value
            ):
                accepted_event = submission_events[-1]

                items.append(
                    timezone.localtime(accepted_event.occured_at).isoformat()
                )

                items.append(
                    all_users[
                        accepted_event.payload.get('accepted_by')
                    ].full_name
                    if accepted_event.payload
                    else None
                )

            print(*items, sep='\t')

    def _get_events(self, rows):
        events_by_submission = collections.defaultdict(list)
        events = models.SubmissionEvent.objects.filter(
            submission__in=[it['id'] for it in rows], event__in=['accepted']
        ).order_by('occured_at')
        for event in events:
            events_by_submission[event.submission.id].append(event)
        return events_by_submission

    def _get_users(self):
        return {user.id: user for user in models.BotUser.objects.all()}
