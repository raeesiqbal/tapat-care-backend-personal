import re

from django.core.exceptions import ValidationError


PASSWORD_POLICY_HELP_TEXT = (
    "Use at least 12 characters and include one lowercase letter, one "
    "uppercase letter, one number, and one special character."
)


PASSWORD_REQUIREMENTS = (
    ("at least 12 characters long", lambda value: len(value) >= 12),
    ("at least one lowercase letter", lambda value: re.search(r"[a-z]", value)),
    ("at least one uppercase letter", lambda value: re.search(r"[A-Z]", value)),
    ("at least one number", lambda value: re.search(r"[0-9]", value)),
    (
        "at least one special character",
        lambda value: re.search(r"[^A-Za-z0-9]", value),
    ),
)


def get_password_policy_error(password):
    missing_requirements = [
        message for message, check in PASSWORD_REQUIREMENTS if not check(password)
    ]

    if not missing_requirements:
        return None

    if len(missing_requirements) == 1:
        return f"Password is missing {missing_requirements[0]}."

    return (
        "Password must include "
        f"{', '.join(missing_requirements[:-1])}, and {missing_requirements[-1]}."
    )


def validate_password_policy(password):
    error_message = get_password_policy_error(password)

    if error_message:
        raise ValidationError(error_message)


class PasswordPolicyValidator:
    def validate(self, password, user=None):
        validate_password_policy(password)

    def get_help_text(self):
        return PASSWORD_POLICY_HELP_TEXT
