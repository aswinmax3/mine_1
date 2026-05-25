from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone
from analyzer.models import PolicyDocument
import datetime

class Command(BaseCommand):
    help = 'Send policy expiry email reminders'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()

        for doc in PolicyDocument.objects.filter(expiry_date__isnull=False, user__isnull=False):
            if not doc.user.email:
                continue

            days_left = (doc.expiry_date - today).days

            if days_left == 30 and not doc.reminder_sent_30:
                self._send(doc, 30)
                doc.reminder_sent_30 = True
                doc.save()

            elif days_left == 15 and not doc.reminder_sent_15:
                self._send(doc, 15)
                doc.reminder_sent_15 = True
                doc.save()

            elif days_left == 7 and not doc.reminder_sent_7:
                self._send(doc, 7)
                doc.reminder_sent_7 = True
                doc.save()

    def _send(self, doc, days):
        send_mail(
            subject=f'⚠️ Policy Expiring in {days} Days — {doc.name}',
            message=f'''Hi {doc.user.username},

Your insurance policy "{doc.name}" expires on {doc.expiry_date}.
That's only {days} days away!

Login to InsureAI to review and take action:
http://127.0.0.1:8000/policy/{doc.pk}/

— InsureAI Team''',
            from_email=None,
            recipient_list=[doc.user.email],
        )
        self.stdout.write(f'Sent {days}-day reminder for: {doc.name}')