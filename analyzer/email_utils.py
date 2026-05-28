from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone


def send_verification_email(user, document):
    now = timezone.now().strftime('%d %B %Y, %I:%M %p IST')
    
    subject = 'Insurance Document Verification - InsureAI'
    message = f"""
Hello {user.first_name or user.username},

Your insurance document has been successfully uploaded and is under verification.

Document Details:
- File: {document.name}
- Uploaded on: {now}
- Status: Under Review

We will notify you once the verification is complete.

Thank you for using InsureAI.

Regards,
InsureAI Team
"""
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def send_coverage_gap_email(user, result_summary):
    subject = 'Your Coverage Gap Analysis - InsureAI'
    message = f"""
Hello {user.first_name or user.username},

Your Coverage Gap Analysis is ready.

Summary:
{result_summary[:500]}...

Log in to InsureAI to view the full report.

Regards,
InsureAI Team
"""
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )