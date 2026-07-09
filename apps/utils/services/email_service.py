from django.core.mail import EmailMultiAlternatives


def send_email_to_user(title, html_message, plaintext_message, from_email, to_email):
    msg = EmailMultiAlternatives(
        subject=title,
        body=plaintext_message,
        from_email=from_email,
        to=[to_email],
    )
    msg.attach_alternative(html_message, "text/html")

    msg.send()
