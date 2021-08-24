import collections
import logging
import traceback
import typing as tp

import telegram as tg
from django.conf import settings
from django.db.models import Max, Count
from telegram import ext as tg_ext
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    Filters,
    MessageHandler,
)

from app import exceptions
from bot import models
from bot import tasks as celery_tasks
from bot.logic import gh, helpers

logger = logging.getLogger(__name__)

(
    GROUP_REQUESTED,
    NAME_REQUESTED,
    GITHUN_LOGIN_REQUESTED,
    KNOWN,
    WAIT_SELECT_ASSIGNMENT,
    WAIT_SELECT_ASSIGNMENT_TASK,
    WAIT_FILE,
    WAIT_SELECT_GROUP_FOR_NEW_ASSIGNMENT,
    WAIT_SELECT_GROUP_FOR_ASSIGNMENTS_LIST,
    WAIT_ASSIGNMENT_TYPE_TO_CREATE,
    WAIT_ASSIGNMENT_NAME,
    WAIT_GIST,
    WAIT_ENABLE_ASSIGNMENT,
    SELECT_ASSIGNMENT_TO_MANAGE,
    WAIT_COMMAND_FOR_ASSIGNMENT,
) = range(15)


def _reply_commands_list(
    user: models.BotUser, message: str, callback: tp.Callable
) -> None:
    commands = helpers.get_user_commands(user)
    callback(message, helpers.inline_keyboard(commands, 'known'))


def start_cancel_command(update: tg.Update, context: tg_ext.CallbackContext):
    user = models.BotUser.get_or_none(update.effective_chat.id)

    if user:
        _reply_commands_list(
            user,
            helpers.get_message('start_to_do'),
            lambda m, kb: context.bot.send_message(
                update.effective_chat.id, m, reply_markup=kb
            ),
        )
        return KNOWN

    groups = models.Groups.objects.order_by('name')

    context.bot.send_message(
        update.effective_chat.id,
        helpers.get_message('from_what_group'),
        reply_markup=helpers.inline_keyboard(
            groups,
            prefix='group_requested',
            alias_col='id',
            column=False,
        ),
    )

    return GROUP_REQUESTED


def me_command(update: tg.Update, context: tg_ext.CallbackContext):
    tg_user = update.effective_user
    user = models.BotUser.get_or_none(update.effective_chat.id)

    msg_alias = 'me_response'
    kwargs = {
        'tg_full_name': tg_user.full_name,
        'tg_username': tg_user.username,
        'tg_id': tg_user.id,
    }

    if user:
        msg_alias = 'me_response_known'
        kwargs.update(
            {
                'groups': ','.join(
                    helpers.escape_markdown(g.name) for g in user.groups.all()
                ),
                'github_login': user.github_login,
                'full_name': user.full_name,
            }
        )

    update.message.reply_text(
        helpers.get_message(msg_alias, **kwargs),
        parse_mode=tg.ParseMode.MARKDOWN_V2,
    )


def group_selected_callback(
    update: tg.Update, context: tg_ext.CallbackContext
):
    query = update.callback_query

    group_id = helpers.extract_data(query.data, 'group_requested')

    users = models.BotUser.objects.filter(
        groups__id=group_id,
        telegram_chat_id__isnull=True,
        role=models.BotUserRole.Student.value,
    )

    if not users:
        query.edit_message_text(
            helpers.get_message('unavailable_for_group'),
        )
        query.answer()
        return GROUP_REQUESTED

    query.edit_message_text(
        helpers.get_message('select_among_group_students'),
        reply_markup=helpers.inline_keyboard(
            sorted(users, key=lambda u: u.full_name),
            'name_requested',
            name_col='full_name',
            alias_col='id',
        ),
    )

    query.answer()

    return NAME_REQUESTED


def name_selected_callback(update: tg.Update, context: tg_ext.CallbackContext):
    query = update.callback_query

    user_id = helpers.extract_data(query.data, 'name_requested')

    context.user_data['user_id'] = user_id

    query.edit_message_text(helpers.get_message('send_me_your_github'))

    query.answer()

    return GITHUN_LOGIN_REQUESTED


def github_login_callback(update: tg.Update, context: tg_ext.CallbackContext):
    github_login = update.message.text

    wait_msg = update.message.reply_text('Секундочку. Проверяю...')

    try:
        if not gh.is_github_user(github_login):
            wait_msg.edit_text(
                helpers.get_message(
                    'no_github_account', github_login=github_login
                ),
                parse_mode=tg.ParseMode.MARKDOWN_V2,
            )
            return GITHUN_LOGIN_REQUESTED
    except exceptions.BackendException:
        wait_msg.edit_text(
            helpers.get_message('cannot_chech_github'),
        )
        return GITHUN_LOGIN_REQUESTED

    user = models.BotUser.objects.get(id=context.user_data['user_id'])

    user.telegram_chat_id = update.effective_chat.id
    user.github_login = github_login

    if update.effective_user.username:
        user.telegram_login = update.effective_user.username

    user.save()

    _reply_commands_list(
        user,
        helpers.get_message('welcome_to_do'),
        lambda m, kb: wait_msg.edit_text(m, reply_markup=kb),
    )

    return start_cancel_command(update, context)


def upload_assignment_callback(
    assignment_type: models.AssignmentType,
    update: tg.Update,
    context: tg_ext.CallbackContext,
):
    query = update.callback_query

    user = models.BotUser.objects.get(
        telegram_chat_id=update.effective_chat.id
    )

    assignments = models.Assignment.get_available_for_user(
        user, assignment_type
    )

    if not assignments:
        query.edit_message_text(helpers.get_message('no_assignments'))
        query.answer()
        return start_cancel_command(update, context)

    msg_alias = f'select_{assignment_type.value}_to_upload'

    context.user_data['assignment_type'] = assignment_type.value

    query.edit_message_text(
        helpers.get_message(msg_alias),
        reply_markup=helpers.inline_keyboard(
            assignments, 'wait_select_assignment', alias_col='id'
        ),
    )

    query.answer()

    return WAIT_SELECT_ASSIGNMENT


def assignment_selected_callback(
    update: tg.Update, context: tg_ext.CallbackContext
):
    query = update.callback_query

    user = models.BotUser.objects.get(
        telegram_chat_id=update.effective_chat.id
    )

    assignment = models.Assignment.objects.get(
        id=helpers.extract_data(
            query.data, 'wait_select_assignment', convert_to=int
        )
    )

    query.edit_message_text(
        helpers.get_message(
            'select_task_to_upload',
            gist_url=assignment.gist_url,
        ),
        reply_markup=helpers.inline_keyboard(
            helpers.build_task_list(assignment, user),
            'wait_select_assignment_task',
        ),
        parse_mode=tg.ParseMode.MARKDOWN_V2,
    )

    context.user_data['user_id'] = user.id
    context.user_data['assignment_id'] = assignment.id

    query.answer()

    return WAIT_SELECT_ASSIGNMENT_TASK


def assignment_task_selected_callback(
    update: tg.Update, context: tg_ext.CallbackContext
):
    query = update.callback_query

    task_id = helpers.extract_data(query.data, 'wait_select_assignment_task')

    context.user_data['task_id'] = task_id

    query.edit_message_text(helpers.get_message('send_me_the_file'))

    query.answer()

    return WAIT_FILE


def document_uploaded(update: tg.Update, context: tg_ext.CallbackContext):
    document = update.message.document

    if not document.file_name.endswith('.py'):
        update.message.reply_text(helpers.get_message('wrong_file_format'))
        return WAIT_FILE

    wait_msg = update.message.reply_text(helpers.get_message('wait_a_second'))

    try:
        objectkey = helpers.upload_file_to_s3(document.get_file())

        user = models.BotUser.objects.get(id=context.user_data['user_id'])
        assignment = models.Assignment.objects.get(
            id=int(context.user_data['assignment_id'])
        )

        submission = models.Submission.objects.create(
            author=user,
            real_assignment=assignment,
            task_id=context.user_data['task_id'],
            status=models.SubmissionStatus.Pending.value,
            objectkey=objectkey,
        )

        celery_tasks.process_file.delay(submission.id)
    except Exception as exc:
        logger.exception(exc)
        wait_msg.edit_text(helpers.get_message('error_retry'))
        return WAIT_FILE

    wait_msg.edit_text(helpers.get_message('file_uploaded'))

    return ConversationHandler.END


def fallback_handler(update: tg.Update, context: tg_ext.CallbackContext):
    update.message.reply_text(helpers.get_message('fallback'))


def error_handler(update: tg.Update, context: tg_ext.CallbackContext):
    tb = ''.join(
        traceback.format_exception(
            None, context.error, context.error.__traceback__
        )
    )

    logger.exception(context.error)

    user = models.BotUser.get_or_none(update.effective_chat.id)

    message = (
        f'Ошибка у пользователя: {user.full_name} '
        f'(@{user.telegram_login})\n\n{tb[-800:]}'
    )

    context.bot.send_message(settings.ADMIN_CHAT_ID, message)

    context.bot.send_message(
        update.effective_chat.id, helpers.get_message('error_retry')
    )


def review_handler(update: tg.Update, context: tg_ext.CallbackContext):
    user = models.BotUser.objects.get(
        telegram_chat_id=update.effective_chat.id
    )

    submissions = models.Submission.objects.filter(
        author__groups__in=user.groups.all(),
        status=models.SubmissionStatus.Review.value,
    ).order_by('real_assignment__type', 'real_assignment__id', 'task_id')

    by_assignment = collections.defaultdict(list)

    limit = 50

    for submission in submissions:
        by_assignment[submission.assignment.id].append(submission)

    for key in by_assignment:
        by_assignment[key].sort(key=lambda s: (s.task_id, s.author.full_name))

    for assignment_id, submissions in by_assignment.items():
        assignment = models.Assignment.objects.get(id=assignment_id)
        assignment_name = helpers.escape_markdown(assignment.name)

        msg = f'*{assignment_name}* \\(review\\: {len(submissions)}\\)\n\n'

        last_task_id = None

        counter = 1
        for submission in submissions[:limit]:
            if last_task_id is not None and last_task_id != submission.task_id:
                msg += '\n'
                counter = 1
            last_task_id = submission.task_id
            msg += (
                f'➜ {counter}\\. [Задача №{submission.task_id} / '
                f'{submission.author.full_name}]'
                f'({submission.pull_url})\n'
            )
            counter += 1
        context.bot.send_message(
            update.effective_chat.id, msg, parse_mode=tg.ParseMode.MARKDOWN_V2
        )


def select_group_handler(
    update: tg.Update,
    context: tg_ext.CallbackContext,
    next_state: int,
    next_handler: tp.Callable,
):
    query = update.callback_query

    user = models.BotUser.get_or_none(update.effective_chat.id)

    groups = user.groups.all()

    if len(groups) == 0:
        query.answer()
        query.edit_message_text(
            'Вы не привязаны ни к одной из групп. Обратитесь к администратору'
        )
        return ConversationHandler.END

    if len(groups) > 1:
        query.answer()
        query.edit_message_text(
            'Выберите группу?',
            reply_markup=helpers.inline_keyboard(
                groups,
                next_handler.__name__,
                alias_col='id',
            ),
        )
        return next_state

    context.user_data['group_id'] = groups[0].id

    return next_handler(update, context)


def group_for_new_assignment_selected(
    update: tg.Update, context: tg_ext.CallbackContext
):
    query = update.callback_query

    if query.data.startswith('group_for_new_assignment_selected'):
        group_id = helpers.extract_data(
            query.data, 'group_for_new_assignment_selected'
        )
        context.user_data['group_id'] = group_id

    query.answer()

    query.edit_message_text(
        'Какого типа задачу вы хотите создать',
        reply_markup=helpers.inline_keyboard(
            [
                {'alias': 'test', 'name': 'Тест'},
                {'alias': 'homework', 'name': 'Домашка'},
            ],
            'wait_assignment_type_to_create',
        ),
    )

    return WAIT_ASSIGNMENT_TYPE_TO_CREATE


def assignment_type_for_create_selected(
    update: tg.Update, context: tg_ext.CallbackContext
):
    query = update.callback_query

    assignment_type = helpers.extract_data(
        query.data, 'wait_assignment_type_to_create'
    )

    context.user_data['assignment_type'] = assignment_type

    text = 'Введите понятное название для '

    if assignment_type == models.AssignmentType.Homework.value:
        text += 'домашки'
    elif assignment_type == models.AssignmentType.Test.value:
        text += 'теста'

    query.answer()

    query.edit_message_text(text)

    return WAIT_ASSIGNMENT_NAME


def new_assignment_name_selected(
    update: tg.Update, context: tg_ext.CallbackContext
):
    context.user_data['assignment_name'] = update.message.text

    update.message.reply_text('Отправьте мне ссылку на gist с заданиями')

    return WAIT_GIST


def new_assignment_gist_selected(
    update: tg.Update, context: tg_ext.CallbackContext
):
    gist_url = update.message.text

    gist_id = models.AssignmentGistCache.parse_gist_url(gist_url)

    if not gist_id:
        update.message.reply_text(
            'Неправильная ссылка на gist. Попробуйте еще раз.'
        )
        return WAIT_GIST

    wait_msg = update.message.reply_text('Секундочку. Скачиваю gist...')

    try:
        models.AssignmentGistCache.cache_gist(gist_id)
    except exceptions.BackendException:
        wait_msg.edit_text(
            'Какой-то неправильный у вас gist. Попробуйте еще раз.'
        )
        return WAIT_GIST

    tasks_count = models.AssignmentGistCache.objects.filter(
        gist_id=gist_id
    ).count()

    if tasks_count == 0:
        wait_msg.edit_text(
            'Не смог найти ни одной задачи в вашем gist. Попробуйте другой.'
        )
        return WAIT_GIST

    wait_msg.edit_text(f'Найдено задач: {tasks_count}')

    group = models.Groups.objects.get(id=int(context.user_data['group_id']))
    user = models.BotUser.get_or_none(update.effective_chat.id)

    assignment_type = context.user_data['assignment_type']

    last_seq = models.Assignment.objects.filter(
        group=group, type=assignment_type
    ).aggregate(Max('seq'))['seq__max']

    assignment = models.Assignment.objects.create(
        group=group,
        name=context.user_data['assignment_name'],
        gist_url=gist_url,
        type=assignment_type,
        owner=user,
        seq=last_seq + 1 if last_seq is not None else 1,
    )

    update.message.reply_text(
        helpers.get_message(
            'assignment_created',
            assignment_type=assignment.type,
            assignment_name=assignment.name,
            assignment_seq=assignment.seq,
            group_name=group.name,
            tasks_count=tasks_count,
            gist_url=gist_url,
        ),
        parse_mode=tg.ParseMode.MARKDOWN_V2,
        reply_markup=helpers.inline_keyboard(
            [
                {'name': 'Да', 'alias': 'true'},
                {'name': 'Нет', 'alias': 'false'},
            ],
            'wait_enable_assignment',
            column=False,
        ),
    )

    context.user_data['assignment_id'] = assignment.id

    return WAIT_ENABLE_ASSIGNMENT


def enable_assignment(update: tg.Update, context: tg_ext.CallbackContext):
    query = update.callback_query
    enable = helpers.extract_data(query.data, 'wait_enable_assignment')

    query.answer()
    query.edit_message_reply_markup(None)

    if enable == 'true':
        assignment = models.Assignment.objects.get(
            id=int(context.user_data['assignment_id'])
        )
        assignment.is_enabled = True
        assignment.save()
        query.message.reply_text('Ассайнмент включен и доступен.')

    return ConversationHandler.END


def group_for_assignments_list_selected(
    update: tg.Update, context: tg_ext.CallbackContext
):
    query = update.callback_query

    if query.data.startswith('group_for_assignments_list_selected'):
        group_id = helpers.extract_data(
            query.data, 'group_for_assignments_list_selected'
        )
        context.user_data['group_id'] = group_id

    query.answer()

    assignments = models.Assignment.objects.filter(
        group__id=int(context.user_data['group_id'])
    ).order_by('type', 'seq')

    if len(assignments) == 0:
        query.edit_message_text('Еще не создано ни одного ассайнмента')
        return ConversationHandler.END

    assignments_items = [
        {
            'name': assignment.name
            + f' ({assignment.type}) '
            + (' ✅' if assignment.is_enabled else ' 🚫'),
            'alias': assignment.id,
        }
        for assignment in assignments
    ]

    query.edit_message_text(
        'Доступные ассайнменты:',
        reply_markup=helpers.inline_keyboard(
            assignments_items, 'select_assignment_to_manage'
        ),
    )

    return SELECT_ASSIGNMENT_TO_MANAGE


def _create_assignment_commands(assignment: models.Assignment):
    on_review = models.Submission.objects.filter(
        real_assignment=assignment, status=models.SubmissionStatus.Review.value
    ).count()

    commands = [
        {
            'name': 'Включен ✅' if assignment.is_enabled else 'Выключен 🚫',
            'alias': 'toogle_enable_assignment',
        }
    ]

    if on_review:
        commands.append(
            {
                'name': f'Задачи на ревью ({on_review})',
                'alias': 'review_submissions',
            }
        )

    return commands


class CountByStatus:
    def __init__(self, status_count_map):
        self.status_count_map = status_count_map

    def __getattr__(self, name):
        return self.status_count_map.get(name, 0)


def select_assignment_to_manage_handler(
    update: tg.Update, context: tg_ext.CallbackContext
):
    query = update.callback_query

    assignment = models.Assignment.objects.get(
        id=helpers.extract_data(query.data, 'select_assignment_to_manage')
    )

    context.user_data['assignment_id'] = assignment.id

    assignment_submissions = models.Submission.objects.filter(
        real_assignment=assignment
    )
    submissions_statuses = {
        item['status']: item['total']
        for item in assignment_submissions.values('status').annotate(
            total=Count('status')
        )
    }

    query.edit_message_text(
        helpers.get_message(
            'assignment_info',
            assignment_name=assignment.name,
            assignment_type=assignment.type,
            assignment_group_name=assignment.group.name,
            assignment_tasks_count=assignment.tasks_count,
            assignment_gist_url=assignment.gist_url,
            assignment_seq=assignment.seq,
            by_status=CountByStatus(submissions_statuses),
        ),
        reply_markup=helpers.inline_keyboard(
            _create_assignment_commands(assignment),
            'manage_assignments',
        ),
        parse_mode=tg.ParseMode.MARKDOWN_V2,
    )

    return WAIT_COMMAND_FOR_ASSIGNMENT


def toogle_enable_assignment(
    update: tg.Update, context: tg_ext.CallbackContext
):
    user = models.BotUser.get_or_none(update.effective_user.id)
    query = update.callback_query

    assignment = models.Assignment.objects.get(
        id=int(context.user_data['assignment_id'])
    )

    if assignment.owner == user:
        assignment.is_enabled = not assignment.is_enabled
        assignment.save()

        context.bot.edit_message_reply_markup(
            update.effective_chat.id,
            update.effective_message.message_id,
            reply_markup=helpers.inline_keyboard(
                _create_assignment_commands(assignment),
                'manage_assignments',
            ),
        )

        query.answer('Готово!')
    else:
        query.answer('Только создатели ассайнмента могут его изменять')

    return WAIT_COMMAND_FOR_ASSIGNMENT


def show_review_submissions(
    update: tg.Update, context: tg_ext.CallbackContext
):
    query = update.callback_query
    query.answer()

    assignment = models.Assignment.objects.get(
        id=int(context.user_data['assignment_id'])
    )

    submissions = models.Submission.objects.filter(
        real_assignment=assignment,
        status=models.SubmissionStatus.Review.value,
    ).order_by('task_id', 'author__last_name', 'author__first_name')

    by_task_id = collections.defaultdict(list)

    for submission in submissions:
        by_task_id[submission.task_id].append(submission)

    limit = 50
    exclamation_mark_threshold = 3

    counter = 0
    msg = ''

    for task_submissions in by_task_id.values():
        for submission in task_submissions:
            if counter >= limit:
                break
            counter += 1
            line = (
                f'➜ [Задача №{submission.task_id} / '
                f'{submission.author.full_name}]'
                f'({submission.pull_url})'
            )
            elapsed = submission.status_elapsed
            seen = submission.seen
            if (
                elapsed and elapsed.days > exclamation_mark_threshold
            ) or not seen:
                elapsed_fmt = helpers.status_elapsed_formatted(
                    elapsed, exclamation_mark_threshold
                )
                if elapsed_fmt:
                    line += f' \\[*{elapsed_fmt}*\\]'
            elif seen:
                line += ' \\[*seen*\\]'
            line += '\n'
            msg += line
        msg += '\n'

    query.edit_message_text(msg, parse_mode=tg.ParseMode.MARKDOWN_V2)

    return ConversationHandler.END


def setup_handlers(dispatcher: tg_ext.Dispatcher):
    conversation = ConversationHandler(
        entry_points=[
            CommandHandler(['cancel', 'start'], start_cancel_command),
        ],
        states={
            KNOWN: [
                CallbackQueryHandler(
                    lambda upd, ctx: upload_assignment_callback(
                        models.AssignmentType.Homework, upd, ctx
                    ),
                    pattern='^known:upload_homework$',
                ),
                CallbackQueryHandler(
                    lambda upd, ctx: upload_assignment_callback(
                        models.AssignmentType.Test, upd, ctx
                    ),
                    pattern='^known:upload_test$',
                ),
                CallbackQueryHandler(review_handler, pattern='^known:review$'),
                CallbackQueryHandler(
                    lambda upd, ctx: select_group_handler(
                        upd,
                        ctx,
                        WAIT_SELECT_GROUP_FOR_NEW_ASSIGNMENT,
                        group_for_new_assignment_selected,
                    ),
                    pattern='^known:create_assignment$',
                ),
                CallbackQueryHandler(
                    lambda upd, ctx: select_group_handler(
                        upd,
                        ctx,
                        WAIT_SELECT_GROUP_FOR_ASSIGNMENTS_LIST,
                        group_for_assignments_list_selected,
                    ),
                    pattern='^known:view_assignments$',
                ),
            ],
            GROUP_REQUESTED: [
                CallbackQueryHandler(
                    group_selected_callback, pattern='^group_requested'
                )
            ],
            NAME_REQUESTED: [
                CallbackQueryHandler(
                    name_selected_callback, pattern='^name_requested'
                )
            ],
            GITHUN_LOGIN_REQUESTED: [
                MessageHandler(
                    Filters.text & ~Filters.command, github_login_callback
                ),
            ],
            WAIT_SELECT_ASSIGNMENT: [
                CallbackQueryHandler(
                    assignment_selected_callback,
                    pattern='^wait_select_assignment',
                )
            ],
            WAIT_SELECT_ASSIGNMENT_TASK: [
                CallbackQueryHandler(
                    assignment_task_selected_callback,
                    pattern='^wait_select_assignment_task',
                )
            ],
            WAIT_FILE: [MessageHandler(Filters.document, document_uploaded)],
            WAIT_SELECT_GROUP_FOR_NEW_ASSIGNMENT: [
                CallbackQueryHandler(
                    group_for_new_assignment_selected,
                    pattern='^group_for_new_assignment_selected',
                )
            ],
            WAIT_ASSIGNMENT_TYPE_TO_CREATE: [
                CallbackQueryHandler(
                    assignment_type_for_create_selected,
                    pattern='^wait_assignment_type_to_create',
                ),
            ],
            WAIT_ASSIGNMENT_NAME: [
                MessageHandler(
                    Filters.text & ~Filters.command,
                    new_assignment_name_selected,
                ),
            ],
            WAIT_GIST: [
                MessageHandler(
                    Filters.text & ~Filters.command,
                    new_assignment_gist_selected,
                ),
            ],
            WAIT_ENABLE_ASSIGNMENT: [
                CallbackQueryHandler(
                    enable_assignment,
                    pattern='^wait_enable_assignment',
                )
            ],
            WAIT_SELECT_GROUP_FOR_ASSIGNMENTS_LIST: [
                CallbackQueryHandler(
                    group_for_assignments_list_selected,
                    pattern='^group_for_assignments_list_selected',
                )
            ],
            SELECT_ASSIGNMENT_TO_MANAGE: [
                CallbackQueryHandler(
                    select_assignment_to_manage_handler,
                    pattern='^select_assignment_to_manage',
                )
            ],
            WAIT_COMMAND_FOR_ASSIGNMENT: [
                CallbackQueryHandler(
                    toogle_enable_assignment,
                    pattern='^manage_assignments:toogle_enable_assignment',
                ),
                CallbackQueryHandler(
                    show_review_submissions,
                    pattern='^manage_assignments:review_submissions',
                ),
            ],
        },
        fallbacks=[
            CommandHandler(['cancel', 'start'], start_cancel_command),
            MessageHandler(Filters.all, fallback_handler),
        ],
        name='conversation',
        persistent=True,
    )

    dispatcher.add_handler(CommandHandler('me', me_command))
    dispatcher.add_handler(conversation)

    dispatcher.add_error_handler(error_handler)
