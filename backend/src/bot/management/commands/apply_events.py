from __future__ import annotations

import dataclasses
import datetime
import json
import typing as tp

from django.core.management.base import BaseCommand
import dateparser

from bot import models
from bot import tasks


@dataclasses.dataclass
class EventItem:
    type: str
    pull_url: str
    body: str
    author: str
    occured_at: datetime.datetime
    repo: str
    ref: tp.Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> EventItem:
        if isinstance(data['occured_at'], str):
            data['occured_at'] = dateparser.parse(data['occured_at'])
        return cls(**data)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def to_json(self) -> str:
        di = self.to_dict()
        di['occured_at'] = self.occured_at.isoformat()
        return di


class BaseEventHandler:
    error = ValueError

    event: EventItem

    def __init__(self, event: EventItem, run: bool):
        self.event = event
        self.run = run

    def __call__(self):
        raise NotImplementedError

    def get_user_and_submission(self):
        submission = models.Submission.objects.filter(
            pull_url=self.event.pull_url
        ).first()

        if not submission:
            raise self.error(f'No submission for pull: {self.event.pull_url}')

        user = models.BotUser.objects.filter(
            github_login__iexact=self.event.author
        ).first()

        if not user:
            raise self.error(f'Unknown user: {self.event.author}')

        return user, submission


class SubmissionCommentHandler(BaseEventHandler):
    _commands = ('/accepted', '/needwork')

    def __call__(self):
        user, submission = self.get_user_and_submission()

        if user.is_staff:
            if self.event.body in self._commands:
                self._process_command(self.event.body, user, submission)
        else:
            self._process_student_text(self.event.body, user, submission)

    def _process_command(
        self, command: str, user: models.BotUser, submission: models.Submission
    ):
        if command == '/needwork':
            if self.run:
                tasks.process_needwork(
                    submission.id,
                    event_dt=self.event.occured_at,
                    need_notify=False,
                )
        elif command == '/accepted':
            if self.run:
                tasks.process_accepted(
                    submission.id,
                    user.id,
                    event_dt=self.event.occured_at,
                    need_notify=False,
                )
        else:
            raise self.error(f'Unknown command: {command}')

    def _process_student_text(
        self, text: str, user: models.BotUser, submission: models.Submission
    ):
        if self.run:
            tasks.process_student_pull_comment(
                submission.id,
                user.id,
                text[:100],
                event_dt=self.event.occured_at,
                need_notify=False,
            )


class SubmissionReviewHandler(SubmissionCommentHandler):
    pass


class SubmissionPushHandler(BaseEventHandler):
    def __call__(self):
        user, submission = self.get_user_and_submission()

        if not user.is_staff:
            if self.run:
                tasks.process_student_push(
                    submission.id,
                    user.id,
                    event_dt=self.event.occured_at,
                    need_notify=False,
                )


class SubmissionCreatedHandler(BaseEventHandler):
    def __call__(self):
        user, submission = self.get_user_and_submission()
        if submission.created_at != self.event.occured_at:
            submission.created_at = self.event.occured_at
            submission.save()


class Command(BaseCommand):
    help = 'Apply events'

    registry = {
        'submission.created': SubmissionCreatedHandler,
        'submission.review': SubmissionReviewHandler,
        'submission.comment': SubmissionCommentHandler,
        'submission.push': SubmissionPushHandler,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.errors = []
        self.ok = 0

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, required=True)
        parser.add_argument('--run', action='store_true', default=False)

    def handle(self, *args, **options):
        run = options['run']
        with open(options['file']) as file:
            for i, line in enumerate(file):
                line = line.strip()
                event = EventItem.from_dict(json.loads(line))
                try:
                    self.registry[event.type](event, run)()
                    self.stdout.write(self.style.SUCCESS(f'# {i + 1}'))
                    self.ok += 1
                except Exception as exc:
                    self.stdout.write(
                        self.style.ERROR(f'ERROR [{event}]: {exc}')
                    )
                    self.errors.append((str(exc), line))

        if self.errors:
            errors_file = '_events_with_errors.jsonl'
            with open(errors_file, 'w') as file:
                for error, line in self.errors:
                    file.write(error + '\t' + line + '\n')
            self.stdout.write(
                self.style.WARNING(
                    f'Events with errors wrote in {errors_file}'
                )
            )

        if self.ok > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Applied successfully: {self.ok}')
            )
