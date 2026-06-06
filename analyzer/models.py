from django.db import models
from django.contrib.auth.models import User


class PolicyDocument(models.Model):
    user = models.ForeignKey(
    User,
    on_delete=models.CASCADE,
    null=True,
    blank=True
)
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='policies/')
    extracted_text = models.TextField(blank=True)
    ai_analysis = models.JSONField(null=True, blank=True)
    health_score = models.IntegerField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateField(null=True, blank=True)
    reminder_sent_30 = models.BooleanField(default=False)
    reminder_sent_15 = models.BooleanField(default=False)
    reminder_sent_7 = models.BooleanField(default=False)
    phone_number = models.CharField(
    max_length=20,
    blank=True,
    help_text="With country code, e.g. +919876543210"
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.user.username}"

    def days_until_expiry(self):
        from datetime import date
        if self.expiry_date:
            return (self.expiry_date - date.today()).days
        return None

    def __str__(self):
        return self.name


class ChatMessage(models.Model):
    policy = models.ForeignKey(PolicyDocument, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10)  # 'user' or 'ai'
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class ClaimAssessment(models.Model):
    policy = models.ForeignKey(PolicyDocument, on_delete=models.CASCADE)
    claim_description = models.TextField()
    result = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


