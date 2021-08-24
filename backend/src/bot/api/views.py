import logging

import telegram as tg
from rest_framework import permissions, request, response, views
from telegram import ext as tg_ext

from bot.logic import tg as tg_logic
from bot.logic import gh


logger = logging.getLogger(__name__)


class TelegramHookView(views.APIView):
    permission_classes = (permissions.AllowAny,)

    updater: tg_ext.Updater
    dispatcher: tg_ext.Dispatcher

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.updater = tg_logic.create_updater()
        self.dispatcher = self.updater.dispatcher

    def post(self, request: request.Request, format=None):
        update = tg.Update.de_json(request.data, self.dispatcher.bot)
        logger.info('Incoming update: %s', update)

        self.dispatcher.process_update(update)

        return response.Response()


class GithubHookView(views.APIView):
    permission_classes = (permissions.AllowAny,)

    dispatcher: gh.EventDispatcher

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dispatcher = gh.EventDispatcher()

    def post(self, request: request.Request, format=None):
        self.dispatcher.dispatch(request.META, request.data)
        return response.Response()
