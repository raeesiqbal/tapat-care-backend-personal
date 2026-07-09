from autoslug import AutoSlugField
from django.db import models

from .base import AbstractBaseModel


class Condition(AbstractBaseModel):
    name = models.CharField(max_length=255, unique=True)
    slug = AutoSlugField(populate_from="name", unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Equipment(AbstractBaseModel):
    name = models.CharField(max_length=255, unique=True)
    slug = AutoSlugField(populate_from="name", unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
