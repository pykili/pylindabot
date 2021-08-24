import json
import random
import string

from rest_framework.test import APIClient

from users.auth import Authenticator
from users.models import UserModel


class DRFClient(APIClient):
    def __init__(self, *args, user=None, admin=False, anon=False, **kwargs):
        super().__init__(*args, **kwargs)

        self.password = None
        if not anon:
            self.auth(user, admin)

    def auth(self, user=None, admin=False):
        self.user = user or self._create_user(admin)

        token = Authenticator().create_user_token(self.user)
        self.credentials(HTTP_AUTHORIZATION=f'Token {token.token}')

    def _create_user(self, admin=False):
        user_opts = {'email': 'user@mail.ru', 'password': 'hackme'}
        if admin:
            user_opts.update(
                {
                    'email': 'admin@mail.ru',
                    'is_staff': True,
                    'is_superuser': False,
                }
            )
        user, created = UserModel.objects.get_or_create(**user_opts)
        if created:
            self.password = ''.join(
                (random.choice(string.hexdigits) for _ in range(0, 6))
            )
            user.set_password(self.password)
            user.save()
        return user

    def logout(self):
        self.credentials()
        super().logout()

    def get(self, *args, **kwargs):
        return self._api_call(
            'get', kwargs.get('expected_code', 200), *args, **kwargs
        )

    def post(self, *args, **kwargs):
        return self._api_call(
            'post', kwargs.get('expected_code', 200), *args, **kwargs
        )

    def put(self, *args, **kwargs):
        return self._api_call(
            'put', kwargs.get('expected_code', 200), *args, **kwargs
        )

    def delete(self, *args, **kwargs):
        return self._api_call(
            'delete', kwargs.get('expected_code', 200), *args, **kwargs
        )

    def _api_call(self, method, expected, *args, **kwargs):
        kwargs['format'] = kwargs.get('format', 'json')
        as_response = kwargs.pop('as_response', False)

        method = getattr(super(), method)
        response = method(*args, **kwargs)

        if as_response:
            return response

        content = self._decode(response)

        ok = response.status_code == expected
        assert ok, f'{response.status_code} == {expected}, {content}'

        return content

    def _decode(self, response):
        if not response.content:
            return None

        content = response.content.decode('utf-8')

        if 'application/json' in response._headers['content-type'][1]:
            return json.loads(content)
        else:
            return content
