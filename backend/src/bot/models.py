import datetime
import enum
import logging
import re
import typing as tp

from django.conf import settings
from django.db import models
from django.db import transaction
from django.utils import timezone


logger = logging.getLogger(__name__)


class BotUserRole(enum.Enum):
    Student = 'student'
    Assistant = 'assistant'
    Teacher = 'teacher'
    Admin = 'admin'


STAFF_ROLES = {
    BotUserRole.Assistant.value,
    BotUserRole.Teacher.value,
    BotUserRole.Admin.value,
}


class SubmissionStatus(enum.Enum):
    Pending = 'pending'
    Processing = 'processing'
    Review = 'review'
    Needwork = 'needwork'
    Accepted = 'accepted'


class AssignmentType(enum.Enum):
    Homework = 'homework'
    Test = 'test'


class BotUser(models.Model):
    first_name = models.TextField()
    last_name = models.TextField()
    role = models.TextField()
    telegram_login = models.TextField(null=True, unique=True)
    telegram_chat_id = models.IntegerField(
        null=True, db_index=True, unique=True
    )
    github_login = models.TextField(null=True, db_index=True, unique=True)

    def __str__(self) -> str:
        return (
            f'BotUser[id={self.id},'
            f'role={self.role},full_name={self.full_name},'
            f'telegram_chat_id={self.telegram_chat_id},'
            f'telegram_login={self.telegram_login}]'
        )

    def __repr__(self) -> str:
        return self.__str__()

    @classmethod
    def get_or_none(cls, telegram_chat_id: int) -> tp.Optional['BotUser']:
        return cls.objects.filter(telegram_chat_id=telegram_chat_id).first()

    @property
    def full_name(self) -> str:
        return f'{self.last_name} {self.first_name}'

    @property
    def group_name(self) -> tp.Optional[str]:
        group = self.groups.first()
        if group:
            return group.name
        return None

    @property
    def groups_names(self) -> str:
        return ','.join(g.name for g in self.groups.all())

    @property
    def is_staff(self) -> bool:
        return self.role in STAFF_ROLES

    def get_assignments_repo_name(self) -> str:
        github_settings = {
            'org': 'pykili',
            'assignments_repo_placeholder': 'assignments_{}',
        }
        placeholder = github_settings['assignments_repo_placeholder']

        return placeholder.format(self.github_login.lower())


class Groups(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.TextField()
    users = models.ManyToManyField(BotUser, related_name='groups')

    def __str__(self) -> str:
        return f'Group[id={self.id},name={self.name}]'

    def __repr__(self) -> str:
        return self.__str__()


class GithubRepository(models.Model):
    name = models.TextField(db_index=True)
    owner = models.ForeignKey(
        BotUser, on_delete=models.CASCADE, related_name='repository'
    )
    url = models.TextField()

    def __str__(self) -> str:
        return (
            f'GithubRepository[name={self.name},owner={self.owner},'
            f'url={self.url}]'
        )

    def __repr__(self) -> str:
        return self.__str__()


class AssignmentGistCache(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['gist_id', 'task_id'], name='gist_id_task_id'
            )
        ]

    gist_id = models.TextField()
    task_id = models.IntegerField()
    content = models.TextField()

    def __str__(self) -> str:
        return (
            f'AssignmentGistCache[gist_id={self.gist_id},'
            f'task_id={self.task_id}]'
        )

    def __repr__(self) -> str:
        return self.__str__()

    @classmethod
    def cache_gist(
        cls, gist_id: str, return_task_id: tp.Optional[int] = None
    ) -> tp.Optional[str]:
        from bot.logic import gh  # to prevent ring dependencies

        filename_pattern = r'([0-9]+)\.md'

        gist = gh.get_gist(gist_id)

        cache = {}

        for filename, gist_file in gist.files.items():
            match = re.match(filename_pattern, filename)
            if not match:
                logger.warning('Bad filename %s in gist %s', filename, gist)
                continue
            cache[int(match.group(1))] = gist_file.content

        logger.info('Cache for storing: %s', cache)

        cls.objects.bulk_create(
            [
                cls(gist_id=gist_id, task_id=task_id, content=content)
                for task_id, content in cache.items()
            ],
            ignore_conflicts=True,
        )

        logger.info('return_task_id: %s', return_task_id)

        if return_task_id is not None:
            return cache[return_task_id]

    @classmethod
    def parse_gist_url(cls, gist_url: str) -> str:
        regexp = r'gist\.github\.com/[^/]+/([a-z0-9]+)'
        match = re.search(regexp, gist_url, re.I)
        if match:
            return match.group(1)
        return None


class Assignment(models.Model):
    name = models.TextField()
    type = models.TextField()
    is_enabled = models.BooleanField(default=False)
    gist_url = models.TextField()
    owner = models.ForeignKey(BotUser, on_delete=models.CASCADE)
    group = models.ForeignKey(Groups, on_delete=models.CASCADE)
    seq = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'type',
                    'group',
                    'seq',
                ],
                name='unq_type_group_seq',
            )
        ]

    @property
    def tasks_count(self):
        gist_id = AssignmentGistCache.parse_gist_url(self.gist_url)
        return AssignmentGistCache.objects.filter(gist_id=gist_id).count()

    @classmethod
    def get_available_for_user(
        cls, user: BotUser, assignment_type: tp.Optional[AssignmentType] = None
    ):
        user_groups = user.groups
        kwargs = {'group__in': user_groups.all(), 'is_enabled': True}
        if assignment_type:
            kwargs['type'] = assignment_type.value
        return cls.objects.filter(**kwargs)

    def __str__(self) -> str:
        return (
            f'Assignment[id={self.id},name={self.name},'
            f'group={self.group.name},seq={self.seq},type={self.type},'
            f'is_enabled={self.is_enabled}]'
        )

    def __repr__(self) -> str:
        return self.__str__()


class SubmissionEvent(models.Model):
    submission = models.ForeignKey(
        'Submission', on_delete=models.CASCADE, related_name='events'
    )
    event = models.TextField()
    occured_at = models.DateTimeField(auto_now_add=timezone.now)
    payload = models.JSONField(null=True)

    def __str__(self) -> str:
        payload_repr = '{{...}}' if self.payload is not None else None
        return (
            f'SubmissionEvent[event={self.event},'
            f'submission_id={self.submission.id},'
            f'occured_at={self.occured_at},payload={payload_repr}]'
        )

    def __repr__(self) -> str:
        return self.__str__()


class Submission(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'author',
                    'assignment_type',
                    'assignment_id',
                    'task_id',
                ],
                name='unq_type_assignment_task',
            )
        ]

    author = models.ForeignKey(BotUser, on_delete=models.CASCADE)
    task_id = models.IntegerField(db_index=True)
    status = models.TextField()
    objectkey = models.TextField()
    created_at = models.DateTimeField(auto_now_add=timezone.now)
    repository = models.ForeignKey(
        GithubRepository, on_delete=models.CASCADE, null=True
    )
    pull_url = models.TextField(null=True, db_index=True)
    git_ref = models.TextField(null=True)

    # Deprecated: will be removed soon
    gist_url = models.TextField(null=True)
    assignment_type = models.TextField(null=True)
    assignment_id = models.IntegerField(db_index=True, null=True)

    # New: rename after removed ^
    real_assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, null=True
    )

    def __str__(self) -> str:
        return (
            f'Submission[id={self.id},status={self.status},'
            f'author={self.author},'
            f'assignment={self.assignment_type}/{self.assignment_id}/'
            f'{self.task_id}]'
        )

    def __repr__(self) -> str:
        return self.__str__()

    @property
    def gist_id(self) -> str:
        return self.gist_url.split('/')[-1]

    @property
    def assignment_name(self) -> str:
        return self.real_assignment.name if self.real_assignment else '-'

    def get_task_content(self) -> str:
        gist_id = AssignmentGistCache.parse_gist_url(
            self.real_assignment.gist_url
        )
        try:
            entry = AssignmentGistCache.objects.get(
                gist_id=gist_id, task_id=self.task_id
            )
            return entry.content
        except AssignmentGistCache.DoesNotExist:
            return AssignmentGistCache.cache_gist(gist_id, self.task_id)

    @transaction.atomic
    def create_event(
        self,
        event: str,
        payload: tp.Optional[dict] = None,
        occured_at: tp.Optional[datetime.datetime] = None,
    ) -> None:
        if payload is not None:
            assert isinstance(payload, dict), 'Payload must be dict'

        event = SubmissionEvent.objects.create(
            submission=self, event=event, payload=payload
        )

        if occured_at is not None:
            event.occured_at = occured_at
            event.save()

        self.events.add(event)
        self.save()

    def get_staff(self):
        staff = BotUser.objects.filter(
            role__in=STAFF_ROLES,
            groups__in=self.author.groups.all(),
        )
        if not settings.DEBUG:
            staff = staff.exclude(id=self.author.id)
        return staff.distinct()

    @property
    def seen(self) -> str:
        return self.events.filter(event__in=['needwork', 'accepted']).exists()

    @property
    def status_elapsed(self) -> tp.Optional[datetime.timedelta]:
        status_event = (
            self.events.filter(event=self.status)
            .order_by('-occured_at')
            .first()
        )
        if not status_event:
            return None
        return timezone.now() - status_event.occured_at


class GithubToken(models.Model):
    token = models.TextField()
    expires_at = models.DateTimeField()
