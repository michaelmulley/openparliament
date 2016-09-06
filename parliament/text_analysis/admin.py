from django.contrib import admin
from parliament.text_analysis.models import TextAnalysis

class TextAnalysisOptions(admin.ModelAdmin):
    search_fields = ('key',)
    list_display = ['key', 'lang', 'updated']

admin.site.register(TextAnalysis, TextAnalysisOptions)