from django.core.mail import send_mail
from django.conf import settings
from email.message import EmailMessage
from email.utils import make_msgid
import smtplib
import ssl

EMAIL_HOST = 'smtp.zoho.com'
EMAIL_PORT = 587  # Zoho SMTP port
EMAIL_HOST_USER = 'behruz@med-crm-service.uz'  # Gmail pochtangiz
EMAIL_HOST_PASSWORD = 'nL618ZrZ6tS0'  # Gmail app password
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER


def send_code_email_(email):
    print("Email:", email)
    subject = "Test Title"
    body = "Test uchun sogdyfo"
    em = EmailMessage()
    print(222)
    em["Message-ID"] = make_msgid()
    em["From"] = EMAIL_HOST_USER
    em["To"] = email
    em["Subject"] = subject
    print(333)
    em.set_content(body, subtype="html")
    print(444)
    # context = ssl.create_default_context()
    with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as smtp:
        # smtp.set_debuglevel(1)  # Bu yordam beradi
        smtp.starttls()  # ⚠️ Muhim
        print(555)
        smtp.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
        print(666)
        smtp.sendmail(EMAIL_HOST_USER, email, em.as_string())
        print(777)


send_code_email_("behruzzo662@gmail.com")