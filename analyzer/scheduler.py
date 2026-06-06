# analyzer/scheduler.py

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from django.core.mail import send_mail
from datetime import date, timedelta

IST = pytz.timezone('Asia/Kolkata')

def send_renewal_reminders():
    """Check DB and send emails for policies expiring in 30, 7, 1 days"""
    from analyzer.models import PolicyDocument   # import here to avoid circular import

    for days in [30, 7, 1]:
        target_date = date.today() + timedelta(days=days)
        expiring = PolicyDocument.objects.filter(expiry_date=target_date)

        for policy in expiring:
            send_mail(
                subject=f"⚠️ Your policy expires in {days} day(s)",
                message=f"Hello,\n\nYour policy '{policy.title}' expires on {policy.expiry_date}.\nPlease renew it soon.",
                from_email='noreply@insuranceai.com',
                recipient_list=[policy.user.email],
                fail_silently=False,
            )
            print(f"[Reminder] Sent to {policy.user.email} — expires in {days} days")


def start():
    """Start the background scheduler — called once when Django starts"""
    scheduler = BackgroundScheduler(timezone=IST)

    # Run every day at 9:00 AM IST
    scheduler.add_job(
        send_renewal_reminders,
        trigger=CronTrigger(hour=9, minute=0, timezone=IST),
        id='renewal_reminder',
        name='Send policy renewal reminders',
        replace_existing=True,
    )

    scheduler.start()
    print("✅ Scheduler started — renewal reminders active (9 AM IST daily)")