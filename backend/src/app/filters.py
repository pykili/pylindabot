from rest_framework.filters import BaseFilterBackend


class OwnerFilter(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        return queryset.filter(owner=request.user)


class OwnerFilterWriteOnly(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return queryset
        return queryset.filter(owner=request.user)


class NotDeletedFilter(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        return queryset.filter(is_deleted=False)
