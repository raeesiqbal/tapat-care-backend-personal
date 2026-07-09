from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from apps.utils.models.base import AbstractBaseModel

class UserManager(BaseUserManager):
    """
    Define a model manager for User model with no username field.
    """
    use_in_migrations = True
    def _create_user(self, email, password, **extra_fields):
        """
        Create and save a User with the given email and password.
        """
        if not email:
            raise ValueError("The given email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save a regular User with the given email and password.
        """
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        user = self._create_user(email, password, **extra_fields)
        user.is_verified = True
        user.save()
        return user


class User(AbstractUser): 
    """
    User model.
    """
    username = None
    email = models.EmailField(_("email address"), unique=True)
    phone = models.CharField(_("Phone"), max_length=20,)
    picture = models.TextField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    email_verification_nonce = models.UUIDField(null=True, blank=True, editable=False)
    email_verification_sent_at = models.DateTimeField(null=True, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    phone_verification_sent_at = models.DateTimeField(null=True, blank=True)
    delete_reason = models.TextField(null=True, blank=True)
    stripe_customer_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
    )
    objects = UserManager()
    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []
    class Meta:
        ordering = ["-id"]
        verbose_name = "User_custom"
        verbose_name_plural = "Users"
    def __str__(self):
        return f"#{self.id} {self.email}"

    def get_role_codes(self):
        """
        Returns normalized role codes for the user.
        Keeps backward compatibility with legacy role_type and staff flags.
        """
        role_codes = set()

        legacy_role = getattr(self, "role_type", None)
        if legacy_role:
            role_codes.add(str(legacy_role).strip().lower())

        if self.is_staff:
            role_codes.add("staff")
        if self.is_superuser:
            role_codes.add("superuser")

        assigned_codes = (
            UserRole.objects.filter(user_id=self.id)
            .select_related("role")
            .values_list("role__code", flat=True)
        )
        for code in assigned_codes:
            if code:
                role_codes.add(code.strip().lower())

        return role_codes 
class Role(AbstractBaseModel):
    code = models.CharField(max_length=50, unique=True)
    def __str__(self):
        return self.code

class UserRole(AbstractBaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE
    )
    def __str__(self):
        return f"{self.user} - {self.role}"
    
class UserAddress(AbstractBaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    line_1 = models.CharField(max_length=255)  # required
    line_2 = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=100)   # no choices now
    state = models.CharField(max_length=100)  # no choices now
    zip = models.CharField(max_length=20)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    def __str__(self):
        return f"{self.user} - {self.line_1}" 

class UserProfile(AbstractBaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile"
    )
    date_of_birth = models.DateField(
        null=True,
        blank=True
    )
    pronouns = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    gender_identity = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )
    ethnicity = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )
    languages = models.JSONField(
        default=list,
        blank=True
    )

    def __str__(self):
        return f"{self.user.email} Profile"
