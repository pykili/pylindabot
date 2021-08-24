import logging

import telegram
from django.conf import settings

from bot import models
from bot.logic import helpers


logger = logging.getLogger(__name__)


def notify_new_submission(submission: models.Submission) -> None:
    bot = telegram.Bot(settings.TELEGRAM_TOKEN)
    author = submission.author

    msg_kwargs = {
        'pull_url': submission.pull_url,
        'task_id': submission.task_id,
        'assignment_id': submission.real_assignment.id,
        'student_full_name': author.full_name,
        'assignment_name': submission.real_assignment.name,
    }

    logger.info('Notifying abount new submission: %s', submission)

    def _notify_author():
        msg = helpers.get_message('submission_created', **msg_kwargs)
        bot.send_message(
            author.telegram_chat_id,
            msg,
            parse_mode=telegram.ParseMode.MARKDOWN_V2,
        )

    def _notify_staff():
        msg = helpers.get_message('submission_created_staff', **msg_kwargs)
        staff = submission.get_staff()
        logger.info('Staff to notify about submission: %s', staff)
        for user in staff:
            bot.send_message(
                user.telegram_chat_id,
                msg,
                parse_mode=telegram.ParseMode.MARKDOWN_V2,
            )

    _notify_author()
    _notify_staff()


def notify_needwork(submission: models.Submission) -> None:
    bot = telegram.Bot(settings.TELEGRAM_TOKEN)
    msg = helpers.get_message(
        'submission_needwork',
        task_id=submission.task_id,
        assignment_name=submission.real_assignment.name,
        pull_url=submission.pull_url,
    )
    bot.send_message(
        submission.author.telegram_chat_id,
        msg,
        parse_mode=telegram.ParseMode.MARKDOWN_V2,
    )


def notify_accepted(submission: models.Submission) -> None:
    bot = telegram.Bot(settings.TELEGRAM_TOKEN)
    msg = helpers.get_message(
        'submission_accepted',
        task_id=submission.task_id,
        assignment_name=submission.real_assignment.name,
        pull_url=submission.pull_url,
    )
    bot.send_message(
        submission.author.telegram_chat_id,
        msg,
        parse_mode=telegram.ParseMode.MARKDOWN_V2,
    )


def notify_student_comment(
    submission: models.Submission,
    commenter: models.BotUser,
    text_fragment: str,
) -> None:
    bot = telegram.Bot(settings.TELEGRAM_TOKEN)

    msg_kwargs = {
        'pull_url': submission.pull_url,
        'task_id': submission.task_id,
        'assignment_id': submission.real_assignment.id,
        'student_full_name': commenter.full_name,
        'assignment_name': submission.real_assignment.name,
    }

    msg = helpers.get_message('comment_from_student', **msg_kwargs)

    staff = submission.get_staff()
    logger.info('Staff to notify about submission: %s', staff)

    for user in staff:
        bot.send_message(
            user.telegram_chat_id,
            msg,
            parse_mode=telegram.ParseMode.MARKDOWN_V2,
        )


def notify_student_push(
    submission: models.Submission, student: models.BotUser
) -> None:
    bot = telegram.Bot(settings.TELEGRAM_TOKEN)

    msg_kwargs = {
        'pull_url': submission.pull_url,
        'task_id': submission.task_id,
        'assignment_id': submission.real_assignment.id,
        'student_full_name': student.full_name,
        'assignment_name': submission.real_assignment.name,
    }

    msg = helpers.get_message('push_from_student', **msg_kwargs)

    staff = submission.get_staff()
    logger.info('Staff to notify about submission: %s', staff)

    for user in staff:
        bot.send_message(
            user.telegram_chat_id,
            msg,
            parse_mode=telegram.ParseMode.MARKDOWN_V2,
        )


def notify_invite_sent(user: models.BotUser, repo_url: str) -> None:
    bot = telegram.Bot(settings.TELEGRAM_TOKEN)
    msg = helpers.get_message('invite_sent', repo_url=repo_url)
    bot.send_message(
        user.telegram_chat_id, msg, parse_mode=telegram.ParseMode.MARKDOWN_V2
    )


def notify_bad_encoding(submission: models.Submission) -> None:
    bot = telegram.Bot(settings.TELEGRAM_TOKEN)
    bot.send_message(
        settings.ADMIN_CHAT_ID, f'Bad encoding. Submission id: {submission.id}'
    )
