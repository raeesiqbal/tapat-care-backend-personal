from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from apps.users.models import Role, User, UserRole
from apps.users.password_policy import validate_password_policy


def validate_password_serializer_value(value):
    try:
        validate_password_policy(value)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.messages)

    return value



class RegisterUserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(write_only=True)
    role = serializers.SlugRelatedField(
        slug_field="code",
        queryset=Role.objects.all(),
        write_only=True,
    )

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "full_name",
            "role",
        ]
        extra_kwargs = {
            "password": {"write_only": True},
        }

    def validate_password(self, value):
        return validate_password_serializer_value(value)

    def validate_role(self, value):
        allowed_roles = {"caregiver", "careseeker", "staff", "superuser"}
        if value.code not in allowed_roles:
            raise serializers.ValidationError("Invalid role.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        role = validated_data.pop("role")
        password = validated_data.pop("password")
        full_name = validated_data.pop("full_name")

        # split full name safely
        parts = full_name.strip().split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""

        user = User.objects.create(
            email=validated_data["email"],
            first_name=first_name,
            last_name=last_name,
        )

        user.set_password(password)

        if role.code in {"staff", "superuser"}:
            user.is_staff = True

        if role.code == "superuser":
            user.is_superuser = True

        user.save()

        UserRole.objects.get_or_create(user=user, role=role)

        return user

class GetMeSerializer(serializers.ModelSerializer):
    phone_verified = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    account_type = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "email",
            "is_verified",
            "picture",
            "delete_reason",
            "phone",
            "phone_verified",
            "roles",
            "account_type",
        ]

    def get_phone_verified(self, obj):
        return bool(obj.phone_verified_at)

    def get_roles(self, obj):
        return sorted(obj.get_role_codes())

    def get_account_type(self, obj):
        return resolve_account_type(obj)

class CreateUserSerializer(serializers.ModelSerializer):
    def validate_password(self, value):
        return validate_password_serializer_value(value)

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "picture",
            "is_verified",
            "phone",

        ]

class UpdateUserSerializer(serializers.ModelSerializer):
    def validate_password(self, value):
        return validate_password_serializer_value(value)

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "picture",
            "is_verified",
            "phone",
        ]

class UpdateProfileSerializer(serializers.ModelSerializer):
    old_password = serializers.CharField(required=False)
    new_password = serializers.CharField(required=False)

    def validate_new_password(self, value):
        return validate_password_serializer_value(value)

    class Meta:
        model = User
        fields = [
            "old_password",
            "new_password",
        ]

class GetUserSerializer(serializers.ModelSerializer):
    phone_verified = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    account_type = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "picture",
            "is_verified",
            "phone",
            "phone_verified",
            "roles",
            "account_type",
        ]

    def get_phone_verified(self, obj):
        return bool(obj.phone_verified_at)

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_roles(self, obj):
        return sorted(obj.get_role_codes())

    def get_account_type(self, obj):
        return resolve_account_type(obj)


def resolve_account_type(user):
    role_codes = set(user.get_role_codes())

    if "caregiver" in role_codes:
        return "caregiver"
    if "careseeker" in role_codes:
        return "careseeker"
    if "superuser" in role_codes or user.is_superuser:
        return "superadmin"
    if "staff" in role_codes or user.is_staff:
        return "superadmin"
    return "careseeker"


class UpdatePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, trim_whitespace=False, write_only=True)
    new_password = serializers.CharField(required=True, trim_whitespace=False, write_only=True)

    def validate_new_password(self, value):
        return validate_password_serializer_value(value)

class ValidatePasswordSerializer(serializers.ModelSerializer):
    password = serializers.CharField()

    class Meta:
        model = User
        fields = ["password"]

ALLOWED_USER_PICTURE_CONTENT_TYPES = {
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
}
MAX_USER_PICTURE_SIZE_BYTES = 5 * 1024 * 1024


class UserPictureSerializer(serializers.Serializer):
    file = serializers.FileField(required=True)
    content_type = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        file = attrs["file"]
        content_type = str(
            attrs.get("content_type") or getattr(file, "content_type", "")
        ).strip().lower()

        if content_type not in ALLOWED_USER_PICTURE_CONTENT_TYPES:
            raise serializers.ValidationError(
                {"file": "Upload a JPG, PNG, WebP, or GIF image."}
            )

        if getattr(file, "size", 0) > MAX_USER_PICTURE_SIZE_BYTES:
            raise serializers.ValidationError(
                {"file": "Profile photo must be 5 MB or smaller."}
            )

        attrs["content_type"] = content_type
        return attrs

class OAuthTokenRequestSerializer(serializers.Serializer):
    username = serializers.EmailField(required=True)
    password = serializers.CharField(required=True)
    grant_type = serializers.ChoiceField(choices=["password"], required=True)
    client_secret = serializers.CharField(required=True)
    client_id = serializers.CharField(required=True)


class RegisterCaregiverSerializer(serializers.ModelSerializer):
    def validate_password(self, value):
        return validate_password_serializer_value(value)

    class Meta:
        model = User
        fields = ["email", "password"]
        extra_kwargs = {
            "password": {"write_only": True},
        }

    def create(self, validated_data):
        password = validated_data.pop("password")

        user = User.objects.create(
            email=validated_data["email"],
        )
        user.set_password(password)
        user.save()
        return user

class RegisterCareseekerSerializer(serializers.ModelSerializer):
    def validate_password(self, value):
        return validate_password_serializer_value(value)
    
    class Meta:
        model = User
        fields = ["email", "password"]
        extra_kwargs = {
            "password": {"write_only": True},
        }

    def create(self, validated_data):
        password = validated_data.pop("password")

        user = User.objects.create(
            email=validated_data["email"],
        )
        user.set_password(password)
        user.save()
        return user

