import datetime
import logging
import typing as tp

from app.celery import celery
from bot import models
from bot.logic import notify
from bot.logic import processing

logger = logging.getLogger(__name__)


@celery.task
def process_file(submission_id: int) -> None:
    processing.start_processing(submission_id)


@celery.task
def process_needwork(
    submission_id: int,
    event_dt: tp.Optional[datetime.datetime] = None,
    need_notify: bool = True,
) -> None:
    submission = models.Submission.objects.get(id=submission_id)

    submission.status = models.SubmissionStatus.Needwork.value
    submission.save()
    submission.create_event('needwork', occured_at=event_dt)

    if need_notify:
        notify.notify_needwork(submission)


@celery.task
def process_accepted(
    submission_id: int,
    accepted_by: int,
    event_dt: tp.Optional[datetime.datetime] = None,
    need_notify: bool = True,
) -> None:
    submission = models.Submission.objects.get(id=submission_id)

    submission.status = models.SubmissionStatus.Accepted.value
    submission.save()
    submission.create_event(
        'accepted', payload={'accepted_by': accepted_by}, occured_at=event_dt
    )

    if need_notify:
        notify.notify_accepted(submission)


@celery.task
def process_student_pull_comment(
    submission_id: int,
    commenter_id: int,
    text_fragment: str,
    event_dt: tp.Optional[datetime.datetime] = None,
    need_notify: bool = True,
) -> None:
    submission = models.Submission.objects.get(id=submission_id)
    commenter = models.BotUser.objects.get(id=commenter_id)

    submission.create_event(
        'comment',
        payload={'text_fragment': text_fragment, 'commenter_id': commenter_id},
        occured_at=event_dt,
    )

    if submission.status == models.SubmissionStatus.Needwork.value:
        submission.status = models.SubmissionStatus.Review.value
        submission.save()
        submission.create_event('review', occured_at=event_dt)

    if need_notify:
        notify.notify_student_comment(submission, commenter, text_fragment)


@celery.task
def process_student_push(
    submission_id: int,
    user_id: int,
    event_dt: tp.Optional[datetime.datetime] = None,
    need_notify: bool = True,
) -> None:
    submission = models.Submission.objects.get(id=submission_id)
    user = models.BotUser.objects.get(id=user_id)

    submission.create_event(
        'push',
        payload={'pusher_id': user.id},
        occured_at=event_dt,
    )

    if submission.status == models.SubmissionStatus.Needwork.value:
        submission.status = models.SubmissionStatus.Review.value
        submission.save()
        submission.create_event('review', occured_at=event_dt)

    if need_notify:
        notify.notify_student_push(submission, user)
