start-backend:
	source .env/bin/activate && cd backend/src && python manage.py runserver

start-celery-worker:
	source .env/bin/activate && cd backend/src && celery --app=app worker --loglevel=INFO --pool=gevent
