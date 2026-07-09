from django.db import models
from apps.utils.models.base import AbstractBaseModel
from autoslug import AutoSlugField

class ServiceCategory(AbstractBaseModel):
    name = models.CharField(max_length=255)
    slug = AutoSlugField(
        populate_from="name",
        unique=True
    )
    is_new = models.BooleanField(default= False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
class Service(AbstractBaseModel):
    service_category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.CASCADE,
        related_name="services"
    )
    name = models.CharField(max_length=255)
    description = models.TextField()
    slug = AutoSlugField(
        populate_from="name",
        unique=True
    )
    is_new = models.BooleanField(default= False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name