import os

import environ


BASE_DIR = environ.Path(__file__) - 2

CACHE_DIR = '/var/cache/pylindabot'

env = environ.Env()

envfile = BASE_DIR('.env')
environ.Env.read_env(envfile)

SECRET_KEY = env.str('SECRET_KEY')

DEBUG = env.bool('DEBUG', False)

ALLOWED_HOSTS = ['*']

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'corsheaders',
]

PROJECT_APPS = [
    'app',
    'bot',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + PROJECT_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CORS_ORIGIN_ALLOW_ALL = DEBUG

ROOT_URLCONF = 'app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'app.wsgi.application'

DATABASES = {'default': env.db('DATABASE_URL')}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': f'django.contrib.auth.password_validation.{validator}'}
    for validator in [
        'UserAttributeSimilarityValidator',
        'MinimumLengthValidator',
        'CommonPasswordValidator',
        'NumericPasswordValidator',
    ]
]

ADMIN_ENABLED = True

APPEND_SLASH = False

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Europe/Moscow'

USE_I18N = True

USE_L10N = True

USE_TZ = True

STATIC_URL = '/static/'

STATIC_ROOT = os.path.join(CACHE_DIR, 'static')

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PAGINATION_CLASS': 'app.pagination.AppPagination',
    'PAGE_SIZE': 50,
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': not DEBUG,
    'formatters': {
        'verbose': {
            'format': '{asctime} {module}.'
            '{funcName}:{lineno} '
            '{levelname}: {message}',
            'style': '{',
        }
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'}
    },
    'loggers': {
        '': {'handlers': ['console'], 'level': 'INFO' if DEBUG else 'INFO'},
        'django': {
            'handlers': [
                # 'console'
            ],
            'level': 'INFO',
            'propagate': True,
        },
        'django.db.backends': {
            'handlers': [
                # 'console'
            ],
            'level': 'DEBUG',
            'propagate': False,
        },
        'celery': {'level': 'INFO', 'handlers': ['console']},
    },
}

YMQ_ENDPOINT = 'message-queue.api.cloud.yandex.net:443'

YMQ_REGION = 'ru-central1'

CELERY_BROKER_URL = env.str('CELERY_BROKER_URL', None)

if CELERY_BROKER_URL is None:  # for production
    YMQ_ACCESS_KEY_ID = env.str('YMQ_ACCESS_KEY_ID')

    YMQ_SECRET_ACCESS_KEY = env.str('YMQ_SECRET_ACCESS_KEY')

    CELERY_BROKER_URL = 'sqs://{}:{}@{}'.format(
        YMQ_ACCESS_KEY_ID, YMQ_SECRET_ACCESS_KEY, YMQ_ENDPOINT
    )

    CELERY_BROKER_TRANSPORT_OPTIONS = {
        'is_secure': True,
        'region': YMQ_REGION,
    }

CELERY_TASK_DEFAULT_QUEUE = 'celery-test' if DEBUG else 'celery'

YC_S3_URL = 'https://storage.yandexcloud.net'

YC_S3_BUCKET = 'pylindabot'

REGION_NAME = 'ru-central1'

TELEGRAM_TOKEN = env.str('TELEGRAM_TOKEN')

TELEGRAM_BOT_S3_BUCKET_PREFIX = 'bot/hws'

AWS_ACCESS_KEY_ID = env.str('AWS_ACCESS_KEY_ID')

AWS_SECRET_ACCESS_KEY = env.str('AWS_SECRET_ACCESS_KEY')

GITHUB_TIMEOUT = 5

GITHUB_ATTEMPTS = 3

GITHUB_APP_ID = env.int('GITHUB_APP_ID')

GITHUB_INSTALLATION_ID = env.int('GITHUB_INSTALLATION_ID')

GITHUB_APP_PEM = env.str('GITHUB_APP_PEM', multiline=True)

BOT_PERSISTENCE_PICKLE_FILE = (
    BASE_DIR('.bot_persistence')
    if DEBUG
    else os.path.join(CACHE_DIR, 'bot_persistence.pickle')
)

ADMIN_CHAT_ID = 0  # FIXME
