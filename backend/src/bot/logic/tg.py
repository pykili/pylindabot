from django.conf import settings
from telegram import ext as telegram_ext

from bot.logic import handlers


def create_updater():
    persistence = telegram_ext.PicklePersistence(
        filename=settings.BOT_PERSISTENCE_PICKLE_FILE
    )
    updater = telegram_ext.Updater(
        settings.TELEGRAM_TOKEN,
        use_context=True,
        persistence=persistence,
    )
    handlers.setup_handlers(updater.dispatcher)

    return updater
