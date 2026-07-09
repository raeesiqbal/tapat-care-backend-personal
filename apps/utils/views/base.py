from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.parsers import FormParser


class ResponseInfo(object):
    def __init__(self, **args):
        self.response = {
            "status_code": args.get("error", 200),
            "data": args.get("data", []),
            "message": args.get("message", "success"),
        }

    def format_response(self, data, message, status_code):
        return {"data": data, "message": message, "status_code": status_code}


class ResponseModelViewSet(viewsets.ModelViewSet):

    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(ResponseModelViewSet, self).__init__(**kwargs)

    def list(self, request, *args, **kwargs):
        response_data = super(ResponseModelViewSet, self).list(request, *args, **kwargs)
        self.response_format["data"] = response_data.data
        if not response_data.data:
            self.response_format["message"] = "List empty"
        return Response(self.response_format)

    def retrieve(self, request, *args, **kwargs):
        response_data = super(ResponseModelViewSet, self).retrieve(
            request, *args, **kwargs
        )
        self.response_format["data"] = response_data.data
        if not response_data.data:
            self.response_format["message"] = "Empty"
        return Response(self.response_format)

    def create(self, request, *args, **kwargs):
        response_data = super(ResponseModelViewSet, self).create(
            request, *args, **kwargs
        )
        self.response_format["data"] = response_data.data
        return Response(self.response_format)

    def update(self, request, *args, **kwargs):
        response_data = super(ResponseModelViewSet, self).update(
            request, *args, **kwargs
        )
        self.response_format["data"] = response_data.data

        return Response(self.response_format)

    def destroy(self, request, *args, **kwargs):
        response_data = super(ResponseModelViewSet, self).destroy(
            request, *args, **kwargs
        )
        self.response_format["data"] = response_data.data
        return Response(self.response_format)


class BaseViewset(ResponseModelViewSet):
    action_serializers = dict()
    action_permissions = dict()
    user_role_queryset = dict()

    def _normalize_role_code(self, role_code):
        if role_code is None:
            return None
        return str(role_code).strip().lower()

    def _role_matches(self, role_key, role_codes):
        if isinstance(role_key, (list, tuple, set, frozenset)):
            for key in role_key:
                normalized_key = self._normalize_role_code(key)
                if normalized_key and normalized_key in role_codes:
                    return True
            return False

        normalized_key = self._normalize_role_code(role_key)
        return bool(normalized_key and normalized_key in role_codes)

    def _resolve_user_role_queryset(self, resolver):
        return resolver(self) if callable(resolver) else resolver

    def _get_user_role_codes(self):
        user = getattr(self.request, "user", None)
        if not user or user.is_anonymous:
            return set()

        if hasattr(self, "_cached_user_role_codes"):
            return self._cached_user_role_codes

        if hasattr(user, "get_role_codes") and callable(user.get_role_codes):
            role_codes = user.get_role_codes()
        else:
            legacy_role = getattr(user, "role_type", None)
            role_codes = (
                {self._normalize_role_code(legacy_role)} if legacy_role else set()
            )

        role_codes = {
            code for code in (self._normalize_role_code(code) for code in role_codes) if code
        }
        self._cached_user_role_codes = role_codes
        return role_codes

    def get_serializer_class(self):
        if self.action and self.action in self.action_serializers:
            return self.action_serializers[self.action]
        else:
            return self.action_serializers["default"]

    def get_permissions(self):
        if self.action and self.action in self.action_permissions:
            self.permission_classes = self.action_permissions[self.action]
        elif "default" in self.action_permissions:
            self.permission_classes = self.action_permissions["default"]

        return super().get_permissions()

    def get_queryset(self):
        if self.user_role_queryset:
            role_specific_queryset = [
                (role_key, resolver)
                for role_key, resolver in self.user_role_queryset.items()
                if role_key != "default"
            ]

            if role_specific_queryset:
                role_codes = self._get_user_role_codes()
                if role_codes:
                    for role_key, resolver in role_specific_queryset:
                        if self._role_matches(role_key, role_codes):
                            return self._resolve_user_role_queryset(resolver)

            if "default" in self.user_role_queryset:
                return self._resolve_user_role_queryset(
                    self.user_role_queryset["default"]
                )

        return super().get_queryset()
