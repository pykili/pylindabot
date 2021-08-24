import datetime
import logging
import typing as tp

from django.conf import settings
import github
import jwt
import requests

from app import exceptions
from app.utils import dates as dates_utils
from bot import models
from bot.logic import gh_events
from bot.logic import notify


logger = logging.getLogger(__name__)


def _generate_jwt():
    now = dates_utils.now_aware().timestamp()
    payload = {
        'iat': int(now),
        'exp': int(now + (10 * 60)),
        'iss': settings.GITHUB_APP_ID,
    }
    pem = settings.GITHUB_APP_PEM
    return jwt.encode(payload, pem, algorithm='RS256').decode()


def _get_or_create_token():
    record = models.GithubToken.objects.filter(
        expires_at__gt=dates_utils.now_aware() + datetime.timedelta(minutes=2)
    ).first()

    if record:
        logger.info('GitHub app token in db and valid -> return')
        return record.token

    models.GithubToken.objects.all().delete()

    logger.info('Cannot find GitHub token locally. Fetching...')

    resp = requests.post(
        (
            f'https://api.github.com/app/installations/'
            f'{settings.GITHUB_INSTALLATION_ID}/access_tokens'
        ),
        headers={
            'Authorization': f'Bearer {_generate_jwt()}',
            'Accept': 'application/vnd.github.v3+json',
        },
    ).json()

    models.GithubToken.objects.create(
        token=resp['token'],
        expires_at=dates_utils.parse_timestring_aware(
            resp['expires_at'], 'utc'
        ),
    )

    return resp['token']


def get_client(anon: bool = False) -> github.Github:
    logger.info('Creating GitHub client. Anon: %s', anon)

    kwargs = {
        'timeout': settings.GITHUB_TIMEOUT,
        'retry': settings.GITHUB_ATTEMPTS,
    }

    if not anon:
        kwargs['login_or_token'] = _get_or_create_token()

    return github.Github(**kwargs)


def get_or_create_assignments_repository(
    org: github.Organization, user: models.BotUser
) -> tp.Tuple[github.Repository.Repository, models.GithubRepository]:
    repo_name = user.get_assignments_repo_name()
    if user.repository.first() is None:
        logger.info('User has no repository: %s. Creating...', repo_name)
        return _create_repository(org, user, repo_name)
    gh_repo = org.get_repo(repo_name)
    db_repo = models.GithubRepository.objects.get(name=gh_repo.name)
    return gh_repo, db_repo


def _create_repository(
    org: github.Organization, user: models.BotUser, repo_name: str
) -> tp.Tuple[github.Repository.Repository, models.GithubRepository]:
    gh_repo = None

    try:
        gh_repo = org.create_repo(
            repo_name,
            private=True,
            has_issues=False,
            has_wiki=False,
            has_projects=False,
        )
    except github.GithubException as exc:
        logger.warning(
            'Exception while creating repo: %s. May be repo already exists?',
            exc,
        )

    if gh_repo is None:
        try:
            gh_repo = org.get_repo(repo_name)
        except github.GithubException as exc:
            logger.exception(
                'Repo %s cannot be created and not found. Fix it manually',
                exc_info=exc,
            )
            raise

    _bootstrap_repo(gh_repo, user)

    db_repo = models.GithubRepository.objects.create(
        name=gh_repo.name, owner=user, url=gh_repo.html_url
    )

    return gh_repo, db_repo


def _bootstrap_repo(repo: github.Repository, user: models.BotUser) -> None:
    logger.info('Bootstraping new repository')

    try:
        repo.get_contents('.bootstrap')
        logger.info('Repo %s already bootstrapped', repo)
        return
    except github.GithubException as exc:
        if exc.status == 404:
            pass
        else:
            raise

    bootstrap_settings = {
        'files': [
            {
                'path': 'README.md',
                'commit_msg': 'create readme file',
                'content': (
                    'Репозитарий для домашних работ, тестов и контрольных.'
                    '\n\nСтудент: **{student_full_name}**'
                    '\n\nГруппа: **{student_group_name}**\n'
                ),
            }
        ],
        "collaborator_permission": "push",
    }

    if bootstrap_settings.get('files'):
        for file in bootstrap_settings['files']:
            content = (
                file['content'].format(
                    student_full_name=user.full_name,
                    student_group_name=user.group_name,
                )
                if file['content']
                else ''
            )
            try:
                repo.create_file(
                    file['path'],
                    file['commit_msg'],
                    content,
                )
            except github.GithubException as exc:
                # In fact this steps is not very important
                logger.warning(exc)

    logger.info('Adding %s to collaborators', user)

    invite = repo.add_to_collaborators(
        user.github_login, bootstrap_settings['collaborator_permission']
    )

    logger.info('Invite: %s', invite)

    if invite:
        notify.notify_invite_sent(user, repo.html_url)

    repo.create_file('.bootstrap', 'initial bootstrap done', '')


def is_github_user(login: str) -> bool:
    anon_client = get_client(anon=True)

    try:
        anon_client.get_user(login)
        return True
    except github.UnknownObjectException:
        return False
    except Exception as exc:
        logger.exception(exc)
        raise exceptions.BackendException


def get_gist(gist_id: str) -> github.Gist.Gist:
    anon_client = get_client(anon=True)
    try:
        return anon_client.get_gist(gist_id)
    except github.GithubException as exc:
        logger.exception(exc)
        raise exceptions.BackendException('GitHub exception: ' + str(exc))


class EventDispatcher:
    def __init__(self):
        self.handlers = [
            gh_events.CommentHandler(),
            gh_events.PushHandler(),
            gh_events.ReviewHandler(),
        ]

    def dispatch(self, headers: dict, payload: dict) -> None:
        logger.debug('headers: %s, payload: %s', headers, payload)

        for handler in self.handlers:
            if handler.is_acceptable(headers, payload):
                logger.info('%s is acceptable. Handle...', handler)
                handler.handle(headers, payload)
