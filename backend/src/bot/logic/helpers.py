import datetime
import logging
import typing as tp
import uuid

from django.conf import settings
from telegram import File, InlineKeyboardButton, InlineKeyboardMarkup
import boto3
from telegram.utils import helpers as telegram_helpers

from bot import models


logger = logging.getLogger(__name__)


def commands_availability(
    command: str, availability_alias: str, user: models.BotUser
) -> bool:
    def _test_availability():
        return (
            len(
                models.Assignment.get_available_for_user(
                    user, models.AssignmentType.Test
                )
            )
            > 0
        )

    if availability_alias == 'test':
        return _test_availability()

    return True


def get_user_commands(user: models.BotUser):
    roles_config = {
        'commands': {
            'upload_homework': {'name': 'Загрузить домашку'},
            'upload_test': {'name': 'Сдать тест', 'availability': 'test'},
            'review': {'name': 'Задачи на review'},
            'create_assignment': {'name': 'Создать ассайнмент'},
            'view_assignments': {'name': 'Ассайнменты'},
        },
        'roles': {
            'student': ['upload_homework', 'upload_test'],
            'assistant': ['view_assignments'],
            'teacher': ['create_assignment', 'view_assignments'],
            'admin': [
                'upload_homework',
                'upload_test',
                'create_assignment',
                'view_assignments',
            ],
        },
    }
    role_commands = roles_config['roles'].get(user.role)

    if not role_commands:
        return []

    for command in role_commands:
        if command not in roles_config['commands']:
            continue

        command_config = roles_config['commands'][command]

        if 'availability' in command_config and not commands_availability(
            command, command_config['availability'], user
        ):
            continue

        yield {
            'alias': command,
            'name': command_config['name'],
        }


def inline_keyboard(
    data: tp.Any,
    prefix: str,
    name_col: str = 'name',
    alias_col: str = 'alias',
    url_col: str = 'url',
    column: bool = True,
    prefix_sep: str = ':',
) -> InlineKeyboardMarkup:
    def _extract_alias_or_url(
        item: tp.Any,
    ) -> tp.Tuple[tp.Optional[str], tp.Optional[str]]:
        alias = url = None

        try:
            alias = (
                item[alias_col]
                if isinstance(item, dict)
                else getattr(item, alias_col)
            )
        except (KeyError, AttributeError):
            pass

        try:
            url = (
                item[url_col]
                if isinstance(item, dict)
                else getattr(item, url_col)
            )
        except (KeyError, AttributeError):
            pass

        if alias is None and url is None:
            raise AssertionError('One of alias or url must be present')

        if alias is not None and url is not None:
            raise AssertionError('Only one of alias or url must be present')

        return alias, url

    buttons = []
    for item in data:
        name = (
            item[name_col]
            if isinstance(item, dict)
            else getattr(item, name_col)
        )
        alias, url = _extract_alias_or_url(item)

        button = (
            InlineKeyboardButton(
                name, callback_data=f'{prefix}{prefix_sep}{alias}'
            )
            if alias is not None
            else InlineKeyboardButton(name, url=url)
        )

        if column:
            button = [button]

        buttons.append(button)

    return InlineKeyboardMarkup(buttons if column else [buttons])


def upload_file_to_s3(file: File) -> str:
    boto_session = boto3.session.Session(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.REGION_NAME,
    )
    s3 = boto_session.client(
        service_name='s3',
        endpoint_url=settings.YC_S3_URL,
    )

    objectkey = f'{settings.TELEGRAM_BOT_S3_BUCKET_PREFIX}/{uuid.uuid4().hex}'

    s3.put_object(
        Bucket=settings.YC_S3_BUCKET,
        Key=objectkey,
        Body=file.download_as_bytearray(),
    )

    return objectkey


def escape_markdown(text: str) -> str:
    return telegram_helpers.escape_markdown(text, version=2)


def get_message(alias: str, escape_kwargs: bool = True, **kwargs):
    logger.info('Getting message for alias: %s', alias)
    messages = {
        'start_to_do': 'Доступные команды:',
        'wait_a_second': 'Секундочку...\n',
        'error_retry': '😢 Произошла ошибка. Попробуйте еще раз.\nЕсли ничего не помогает, жмите /cancel.\n',
        'fallback': 'Вы делаете что-то, что я не ожидаю в данный момент 😬. \nПопробуйте /cancel чтобы начать заново.\n',
        'welcome_to_do': 'Приятно познакомиться! Выбирайте, что делать:\n',
        'from_what_group': 'Давайте знакомиться! Из какой вы группы?\n',
        'unavailable_for_group': 'Студентам этой группы еще недоступен бот или уже все дома. Попробуйте зайти позже.\n',
        'select_among_group_students': 'Класс! Найдите себя среди студентов группы:\n',
        'send_me_your_github': 'Отправьте мне ваш логин на github.com\n',
        'no_github_account': 'Такого аккаунта нет на github: *{github_login}*\nВидимо, вы что\\-то не то ввели 😔\nПопробуйте еще раз\n',
        'cannot_chech_github': 'Что-то пока не могу проверить ваш аккаунт на github.\nПопробуйте чуть-чуть позже.\n',
        'no_assignments': 'Пока нечего сдавать. Отдыхайте\n',
        'select_homework_to_upload': 'Какую домашку вы хотите сдать?\n',
        'select_test_to_upload': 'Какой тест хотите сдать?\n',
        'select_task_to_upload': 'Какую задачу хотите сдать?\nВсе задачи по [ссылке]({gist_url})\n',
        'send_me_the_file': 'Отправьте мне один файл с решенной задачей с расширением .py\n',
        'wrong_file_format': 'Присланный вами файл не выглядит как скрипт на python. Проверьте, что шлете именно скрипт на python с расширением .py\n',
        'file_uploaded': 'Ваша посылка принята в обработку. Это может занять некоторое время. Подождите ⏳\n',
        'submission_created': 'Для задачи №{task_id} \\(*{assignment_name}*\\) создан новый [pull request]({pull_url})\\. Заходите\\.\n',
        'submission_created_staff': '🎁\nПришло новое решение\\!\nЗадача *№{task_id}* \\({assignment_name}\\)\nСтудент: *{student_full_name}*\n[Ссылка]({pull_url})\n',
        'submission_needwork': '🤔\nПо задаче *№{task_id}* \\({assignment_name}\\)\\ нужны правочки\\.\n[Ссылка]({pull_url})\n',
        'submission_accepted': '🎉\nЗадачу *№{task_id}* \\(**{assignment_name}**\\) приняли\\.\nПосмотрите\\, может вам оставили какой\\-нибудь дельный комментарий\\.\n[Ссылка]({pull_url})\n',
        'comment_from_student': '[Комментарий]({pull_url}) от {student_full_name} в задаче №{task_id} \\({assignment_name}\\)\\.\n',
        'push_from_student': '{student_full_name} внес изменения в код задачи №{task_id} \\({assignment_name}\\)\\.\n[Ссылка]({pull_url})\\.\n',
        'invite_sent': 'Для вас был создан [новый репозиторий]({repo_url}) на GitHub\\. Чтобы получить туда доступ нужно **принять приглашение**, отправленное вам на почту\\. Почтовый адрес тот, который вы указывали в своем профиле на GitHub\\.\n',
        'assignment_created': 'Новый ассайнмент создан\\.\n\nТип: *{assignment_type}*\\.\nНазвание: *{assignment_name}*\\.\nПорядковый номер: *{assignment_seq}*\\.\nГруппа: *{group_name}*\\.\nКоличество задач: *{tasks_count}*\\.\nGist: {gist_url}\\.\n\nТекст заданий из Gist был закеширован\\. \nЧтобы поменять текст перезагрузите gist через редактирование ассайнмента\\.\n\nВаш ассайнмент создан\\, но студенты его не видят\\. **Включить ассайнмент**\\?\n',
        'assignment_info': 'Название: *{assignment_name}*\\.\nТип: *{assignment_type}*\\.\nПорядковый номер: *{assignment_seq}*\\.\nГруппа: *{assignment_group_name}*\\.\nКоличество задач: *{assignment_tasks_count}*\\.\nGist: {assignment_gist_url}\\.\n\n**Задачи по статусам:**\n \\- review: {by_status.review}\n \\- needwork: {by_status.needwork}\n \\- accepted: {by_status.accepted}\n',
        'me_response': 'Имя в telegram: *{tg_full_name}*\nЛогин telegram: *{tg_username}*\nTelegram ID: `{tg_id}`\n',
        'me_response_known': 'Имя в telegram: *{tg_full_name}*\nЛогин telegram: *{tg_username}*\nTelegram ID: `{tg_id}`\n\nГруппы: *{groups}*\nGitHub login: `{github_login}`\nИмя в ведомости: *{full_name}*\n',
    }

    if escape_kwargs:
        for key in kwargs:
            if isinstance(kwargs[key], str):
                kwargs[key] = escape_markdown(kwargs[key])

    message = messages[alias].format(**kwargs)
    return message


def extract_data(
    data: str,
    prefix: str,
    prefix_sep: str = ':',
    convert_to: tp.Optional[tp.Callable] = None,
) -> str:
    prefix_with_sep = prefix + prefix_sep

    if not data.startswith(prefix_with_sep):
        raise ValueError(f'{data} not startswith {prefix_with_sep}')

    new_start = len(prefix_with_sep)
    clean_data = data[new_start:]

    if convert_to is not None:
        return convert_to(clean_data)

    return clean_data


def build_task_list(
    assignment: models.Assignment, user: models.BotUser
) -> tp.List[dict]:
    submissions = models.Submission.objects.filter(
        author=user,
        real_assignment=assignment,
    )

    task_id_to_submission_map = {
        submission.task_id: submission for submission in submissions
    }

    def _create_task_name(
        task_id: int, submission_status: tp.Optional[str]
    ) -> str:
        ret = f'№ {task_id}'
        if submission_status is not None:
            ret += f' [{submission_status}]'
        return ret

    for i in range(assignment.tasks_count):
        task_id = i + 1
        task_submission = task_id_to_submission_map.get(task_id)
        status = task_submission.status if task_submission else None

        ret = {'name': _create_task_name(task_id, status)}

        if status is None:
            ret.update({'alias': task_id})
        elif task_submission.pull_url is not None:
            ret.update({'url': task_submission.pull_url})
        else:
            # For tasks in processing stage
            continue

        yield ret


def status_elapsed_formatted(
    elapsed_time: datetime.timedelta,
    threshold: int,
) -> tp.Optional[str]:
    if not elapsed_time:
        return None

    days = elapsed_time.days
    hours = elapsed_time.seconds // 3600

    if days > threshold:
        return f'{days}d❗️'

    if days > 0:
        return f'{days}d'

    if hours > 0:
        return f'{hours}h'

    return None
