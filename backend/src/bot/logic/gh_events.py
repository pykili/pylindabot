import abc
import logging
import typing as tp

from bot import models
from bot import tasks


logger = logging.getLogger(__name__)


COMMANDS = {'/accepted', '/needwork'}


class BaseEventHandler(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def is_acceptable(self, headers: dict, payload: dict) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def handle(self, headers: dict, payload: dict) -> None:
        raise NotImplementedError


class CommentHandler(BaseEventHandler):
    def is_acceptable(self, headers: dict, payload: dict) -> bool:
        return 'comment' in payload

    def handle(self, headers: dict, payload: dict) -> None:
        pull = payload.get('issue') or payload.get('pull_request')

        if not pull:
            logger.warning('No issue or pull_request field. Exit')
            return

        if payload.get('action') != 'created':
            logger.info('Action %s != created. Exit', payload.get('action'))
            return

        submission = models.Submission.objects.filter(
            pull_url=pull['html_url']
        ).first()

        if not submission:
            logger.info('No submission for pull: %s. Exit', pull['html_url'])
            return

        comment = payload['comment']['body']
        author = payload['comment']['user']['login']

        user = models.BotUser.objects.filter(
            github_login__iexact=author
        ).first()

        if not user:
            logger.info('Unregistered user: %s. Exit', user)

        if comment in COMMANDS and user.is_staff:
            self._process_command(comment, payload, submission, user)
        else:
            self._process_text(comment, payload, submission, user)

    def _process_text(
        self,
        text: str,
        payload: dict,
        submission: models.Submission,
        commenter: models.BotUser,
    ) -> None:
        if commenter.is_staff:
            logger.info('Some comments from staff. Waiting for commands')
            return

        if text is None:
            logger.info('No text in comment. Exit.')
            return

        tasks.process_student_pull_comment.delay(
            submission.id, commenter.id, text[:100]
        )

    def _process_command(
        self,
        command: str,
        payload: dict,
        submission: models.Submission,
        commenter: models.BotUser,
    ) -> None:
        if command == '/needwork':
            self._needwork_command(payload, submission, commenter)
        elif command == '/accepted':
            self._accepted_command(payload, submission, commenter)

    def _needwork_command(
        self,
        payload: dict,
        submission: models.Submission,
        commenter: models.BotUser,
    ) -> None:
        if not commenter.is_staff:
            logger.info('User: %s is not staff. Exit', commenter)

        tasks.process_needwork.delay(submission.id)

    def _accepted_command(
        self,
        payload: dict,
        submission: models.Submission,
        commenter: models.BotUser,
    ) -> None:
        if not commenter.is_staff:
            logger.info('User: %s is not staff. Exit', commenter)

        tasks.process_accepted.delay(submission.id, commenter.id)


class PushHandler(BaseEventHandler):
    def is_acceptable(self, headers: dict, payload: dict) -> bool:
        return headers.get('HTTP_X_GITHUB_EVENT') == 'push'

    def handle(self, headers: dict, payload: dict) -> None:
        logger.info(
            'Trying to find submission with ref: %s and repository: %s',
            payload['ref'],
            payload['repository']['name'],
        )

        submission = models.Submission.objects.filter(
            git_ref=payload['ref'],
            repository__name=payload['repository']['name'],
        ).first()

        logger.info('Found submission: %s', submission)

        if not submission:
            return

        pusher = models.BotUser.objects.filter(
            github_login__iexact=payload['pusher']['name']
        ).first()

        if not pusher:
            logger.info('Unregistered pusher: %s. Exit', pusher)
            return

        if not pusher.is_staff:
            tasks.process_student_push.delay(submission.id, pusher.id)


class ReviewHandler(BaseEventHandler):
    def is_acceptable(self, headers: dict, payload: dict) -> bool:
        return (
            'review' in payload
            and 'pull_request' in payload
            and payload.get('action') == 'submitted'
        )

    def handle(self, headers: dict, payload: dict) -> None:
        pull = payload['pull_request']

        submission = models.Submission.objects.filter(
            pull_url=pull['html_url']
        ).first()

        if not submission:
            logger.info('No submission for pull: %s. Exit', pull['html_url'])
            return

        review = payload['review']

        user = models.BotUser.objects.filter(
            github_login__iexact=review['user']['login']
        ).first()

        if not user:
            logger.info('Unregistered user: %s. Exit', review['user']['login'])
            return

        if not user.is_staff:
            logger.info('Not staff user: %s. Exit', user)
            return

        state = payload['review'].get('state')

        if state == 'changes_requested':
            logger.info('Processing needwork')
            tasks.process_needwork.delay(submission.id)
        elif state == 'approved':
            logger.info('Processing accepted')
            tasks.process_accepted.delay(submission.id, user.id)
        elif state == 'commented':
            logger.info('Processing comment')
            self._proccess_comment(review.get('body'), submission, user)
        else:
            logger.info('Unsupported review state: %s', state)

    def _proccess_comment(
        self,
        comment: tp.Optional[str],
        submission: models.Submission,
        user: models.BotUser,
    ) -> None:
        if not comment:
            logger.info('Comment is empty. Exit...')
            return
        if comment == '/needwork':
            tasks.process_needwork.delay(submission.id)
        elif comment == '/accepted':
            tasks.process_accepted.delay(submission.id, user.id)
        else:
            logger.info('Comment is just text. Exit...')
