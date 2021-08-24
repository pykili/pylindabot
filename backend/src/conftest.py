import copy
import os
import json
import pathlib

import pytest

from app.test.api_client import DRFClient
from tasks.tests import consts
from users.models import UserModel


@pytest.fixture
def api(db):
    return DRFClient()


@pytest.fixture
def anon(db):
    return DRFClient(anon=True)


@pytest.fixture
def admin(db):
    return DRFClient(admin=True)


@pytest.fixture
def add_tasks(api):
    def _wrapper(*, data=None, count=1, client=None, expected_code=201):
        client = client or api

        if data is None:
            data = copy.deepcopy(consts.DEFAULT_TASK_CREATE_REQUEST)

        tasks = [
            client.post('/api/tasks', data=data, expected_code=expected_code)
            for _ in range(count)
        ]
        if count == 1:
            return tasks[0]
        return tasks

    return _wrapper


@pytest.fixture
def another(db):
    opts = {'email': 'another@mail.ru', 'password': 'hackme'}
    user, _ = UserModel.objects.get_or_create(**opts)
    return DRFClient(user=user)


@pytest.fixture
def get_path(request):
    def _get_path(filename):
        if os.path.isabs(filename):
            return filename
        loc = pathlib.Path(request.fspath)
        target = loc.parent.joinpath('static', loc.stem, filename)
        if target.exists():
            return str(target)
        raise FileNotFoundError(target)

    return _get_path


@pytest.fixture
def read_file(get_path):
    def _wrapper(filename):
        with open(get_path(filename)) as file:
            return file.read()

    return _wrapper


@pytest.fixture
def load_json(get_path):
    def _wrapper(filename):
        with open(get_path(filename)) as file:
            return json.load(file)

    return _wrapper
