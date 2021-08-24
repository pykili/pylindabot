from django.core.management.base import BaseCommand

from bot.logic import tg


class Command(BaseCommand):
    help = 'Start polling with telegram bot'

    def handle(self, *args, **options):
        updater = tg.create_updater()

        updater.start_polling()
        updater.idle()
