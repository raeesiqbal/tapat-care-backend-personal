# imports
from django.dispatch import Signal
from django.db import models
from django.db.models import DateTimeField, ForeignKey, SET_NULL
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

post_archive = Signal()
post_unarchive = Signal()


# models
class AbstractBaseModel(models.Model):
    created_by = ForeignKey(
        "users.User",
        on_delete=SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created_by"
    )
    created_at = DateTimeField(default=timezone.now)
    updated_at = DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-id"]
