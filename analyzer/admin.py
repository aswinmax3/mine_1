from django.contrib import admin

from .models import PolicyDocument, ChatMessage, ClaimAssessment


@admin.register(PolicyDocument)
class PolicyDocumentAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'health_score',
        'uploaded_at',
    )
    search_fields = ('name',)
    list_filter = ('health_score', 'uploaded_at')


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('policy', 'role', 'created_at')
    list_filter = ('role', 'created_at')


@admin.register(ClaimAssessment)
class ClaimAssessmentAdmin(admin.ModelAdmin):
    list_display = ('policy', 'created_at')
    list_filter = ('created_at',)

