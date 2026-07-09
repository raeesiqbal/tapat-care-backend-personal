# imports
from django.core.signing import TimestampSigner
from django.conf import settings
from django.db.models import Q
from django.template.defaultfilters import slugify
from django.utils.crypto import get_random_string
from datetime import date

# from apps.utils.tasks import send_email_to_user
from django.template.loader import render_to_string

# models
# from apps.users.models import VerificationToken


def unique_slugify(Model, str_to_slug, id):
    unique_slug = slugify(str_to_slug)
    while Model.objects.filter(Q(slug=unique_slug), ~Q(id=id)).exists():
        unique_slug = unique_slug + "-" + get_random_string(length=4)
    return unique_slug


# def user_verify_account(user):
#     # Generate token
#     token = TimestampSigner().sign(str(user.id))
#     # Create VerificationToken
#     VerificationToken.objects.create(user=user, token=token)
#     # Sending verify email
#     url = settings.FRONTEND_URL
#     context = {
#         "full_name": "{} {}".format(user.first_name.title(), user.last_name.title()),
#         "year": date.today().year,
#         "verify_account_url": "{}/verify-account?token={}".format(url, token),
#     }
#     send_email_to_user.delay(
#         "Verify your account",
#         render_to_string("emails/verify_account/verify-account.html", context),
#         render_to_string("emails/reset_password/user_reset_password.txt", context),
#         user.email,
#     )
#     return True
