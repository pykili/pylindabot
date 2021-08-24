import logging

from django.conf import settings
import github
import chardet
import boto3

from bot import models
from bot.logic import gh
from bot.logic import notify


logger = logging.getLogger(__name__)


def start_processing(submission_id: int, need_notify: bool = True) -> None:
    github_client = gh.get_client()
    github_settings = {
        'org': 'pykili',
        'assignments_repo_placeholder': 'assignments_{}',
    }

    submission = models.Submission.objects.get(id=submission_id)

    logger.info('Start processing %s', submission)

    if submission.status not in [
        models.SubmissionStatus.Pending.value,
        models.SubmissionStatus.Processing.value,
    ]:
        logger.info('Incorrect status for handling. Exit')
        return

    logger.info('Set status processing')
    submission.status = models.SubmissionStatus.Processing.value
    submission.save()

    user = submission.author

    org = github_client.get_organization(github_settings['org'])

    logger.info('Loaded github organization: %s', org)

    gh_repo, db_repo = gh.get_or_create_assignments_repository(org, user)

    submission_content = extract_submission_content(submission)

    ref, branch = create_new_branch(gh_repo, submission)

    logger.info('Creating file with solution in the new branch...')

    solution_file = (
        f'{submission.real_assignment.type}/'
        f'{submission.real_assignment.seq}/'
        f'{submission.task_id}/'
        f'solution.py'
    )

    try:
        gh_repo.create_file(
            solution_file,
            'add solution file',
            submission_content,
            branch=branch,
        )
    except github.GithubException as exc:
        logger.warning(
            'Exception while creating file: %s. May be file exists?', exc
        )
        try:
            gh_repo.get_contents(solution_file, branch)
        except github.GithubException:
            logger.exception(
                'Cannot create file %s and it is not exist. Raise...',
                solution_file,
            )
            raise

    logger.info('Creating pull request...')

    new_pull_settings = {
        'title': '[{assignment_type}] / {assignment_name} / Задача №{task_id}\n',
        'base_branch': 'main',
        'body': '{task_content}\n\n---\n\n**Студент:** {author_full_name}\n\n**Группа:** {author_group_name}\n',
    }

    format_kwargs = prepare_formatting_kwargs(submission, user)

    pull = gh_repo.create_pull(
        title=new_pull_settings['title'].format(**format_kwargs),
        base=new_pull_settings['base_branch'],
        body=new_pull_settings['body'].format(**format_kwargs),
        head=branch,
    )

    logger.info('New pull request: %s', pull)
    logger.info('Saving state in submission...')

    submission.status = models.SubmissionStatus.Review.value
    submission.repository = db_repo
    submission.pull_url = pull.html_url
    submission.git_ref = ref

    submission.save()

    submission.create_event('review')

    if need_notify:
        notify.notify_new_submission(submission)


def extract_submission_content(submission: models.Submission) -> str:
    boto_session = boto3.session.Session(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.REGION_NAME,
    )
    s3 = boto_session.client(
        service_name='s3',
        endpoint_url=settings.YC_S3_URL,
    )

    object_ = s3.get_object(
        Bucket=settings.YC_S3_BUCKET, Key=submission.objectkey
    )
    body = object_['Body'].read()

    detection_result = chardet.detect(body)

    logger.info(
        f'Body of {submission} encoding detection result: '
        f'{detection_result}'
    )

    candidates = []

    if detection_result['encoding'] and detection_result['confidence'] > 0.8:
        candidates.append(detection_result['encoding'].lower())

    candidates.extend(['utf-8', 'windows-1251'])

    logger.info(f'Encoding candidates: {candidates}')

    for encoding in candidates:
        try:
            content = body.decode(encoding)
            logger.info(f'Selected encoding: {encoding}, content: {content}')
            return content
        except Exception as exc:
            logger.warning(exc)
            continue

    notify.notify_bad_encoding(submission)

    raise Exception('Bad encoding')


def create_new_branch(
    gh_repo: github.Repository.Repository, submission: models.Submission
):
    default_branch = gh_repo.get_branch(gh_repo.default_branch)
    default_branch_sha = default_branch.commit.sha

    logger.info(
        'Default branch: %s with sha: %s', default_branch, default_branch_sha
    )

    new_branch = (
        f'assignments'
        f'-{submission.real_assignment.type}'
        f'-{submission.real_assignment.seq}'
        f'-{submission.task_id}'
    )

    logger.info('New branch for submission: %s', new_branch)

    ref = f'refs/heads/{new_branch}'

    try:
        gh_repo.create_git_ref(ref, default_branch_sha)
    except github.GithubException as exc:
        if exc.status == 422:
            pass
        else:
            raise

    return ref, new_branch


def prepare_formatting_kwargs(
    submission: models.Submission, user: models.BotUser
) -> dict:
    return {
        'assignment_type': submission.real_assignment.type,
        'assignment_name': submission.real_assignment.name,
        'assignment_id': submission.real_assignment.id,
        'assignment_gist': submission.real_assignment.gist_url,
        'task_id': submission.task_id,
        'author_full_name': submission.author.full_name,
        'author_group_name': submission.author.groups.first().name,
        'task_content': submission.get_task_content(),
    }
