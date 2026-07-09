from rest_framework.serializers import ModelSerializer

def has_field(model, fieldname, approx=True):
    if approx:
        return hasattr(model, fieldname)
    return list(filter(lambda x: x.name == fieldname, model._meta.fields))

class DummyRequest:
    user = None

class BaseSerializer(ModelSerializer):
    user_role_fields = dict()

    class Meta:
        lookup_field = "id"

    def get_field_names(self, declared_fields, info):
        fields = super().get_field_names(declared_fields, info)
        if "id" not in fields:
            fields.append("id")

        return fields

    def _get_calling_user(self, default=None):
        user = self.context.get("request", DummyRequest()).user
        return user if user else default

    def _get_calling_user_id(self, default=None):
        user = self.context.get("request", DummyRequest()).user
        return user.id if user else default

    def update(self, instance, validated_data):
        # if self.context.get('request') and has_field(self.Meta.model, 'updated_by'):
        #     instance.updated_by_id = self._get_calling_user_id()
        # validated_data.pop('created_by_id', None)
        return super().update(instance, validated_data)

    def create(self, validated_data):
        # if self.context.get('request') and has_field(self.Meta.model, 'created_by'):
        #     validated_data['created_by_id'] = self._get_calling_user_id()
        # if self.context.get('request') and has_field(self.Meta.model, 'updated_by'):
        #     validated_data['updated_by_id'] = self._get_calling_user_id()
        return super().create(validated_data)
