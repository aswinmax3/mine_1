from django.contrib import admin
from .models import InsuranceDocument


@admin.register(InsuranceDocument)
class InsuranceDocumentAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'document_type',
        'policy_number',
        'premium_amount',
        'coverage_amount',
        'risk_level',
        'uploaded_at',
    )

    search_fields = ('title', 'policy_number', 'document_type')
    list_filter = ('document_type', 'risk_level', 'uploaded_at')