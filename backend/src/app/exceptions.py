from django.utils.translation import gettext as _
from rest_framework import exceptions as drf_exceptions
from rest_framework import status


class BackendException(drf_exceptions.APIException):
    pass


class EmailAlreadyExists(drf_exceptions.ValidationError):
    default_detail = _('Email already exists')


class AuthenticationFailed(drf_exceptions.AuthenticationFailed):
    pass


class NotFound(drf_exceptions.NotFound):
    pass


class PermissionDenied(drf_exceptions.PermissionDenied):
    pass


class Conflict(drf_exceptions.APIException):
    status_code = status.HTTP_409_CONFLICT
