from django import forms
from .models import InsuranceDocument


class InsuranceDocumentForm(forms.ModelForm):
    class Meta:
        model = InsuranceDocument

        fields = [
            'title',
            'document',
            'age',
            'sex',
            'bmi',
            'children',
            'smoker',
            'region',
        ]

        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter document title'
            }),

            'document': forms.FileInput(attrs={
                'class': 'form-control'
            }),

            'age': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter age'
            }),

            'sex': forms.Select(
                choices=[
                    ('', 'Select sex'),
                    ('male', 'Male'),
                    ('female', 'Female'),
                ],
                attrs={'class': 'form-control'}
            ),

            'bmi': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter BMI'
            }),

            'children': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Number of children'
            }),

            'smoker': forms.Select(
                choices=[
                    ('', 'Smoker?'),
                    ('yes', 'Yes'),
                    ('no', 'No'),
                ],
                attrs={'class': 'form-control'}
            ),

            'region': forms.Select(
                choices=[
                    ('', 'Select region'),
                    ('northeast', 'Northeast'),
                    ('northwest', 'Northwest'),
                    ('southeast', 'Southeast'),
                    ('southwest', 'Southwest'),
                ],
                attrs={'class': 'form-control'}
            ),
        }