from django.db import models
from django.utils.safestring import mark_safe

from markdown import markdown

class Summary(models.Model):
    """
    Computer-generated summaries of House transcripts.
    """
    summary_type = models.CharField(max_length=30, choices=[
        ('stage_2', 'Speeches at second reading'),
        ('stage_3', 'Speeches at third reading'),
        ('stage_report', 'Speeches at report stage'),
    ])
    # This is a string to identify what's being summarized. Generally
    # it'll be the URL of the thing being summarized.
    identifier = models.CharField(max_length=255, db_index=True)

    summary_text = models.TextField()

    summarized_statement_count = models.IntegerField()
    latest_statement_date = models.DateField()
    created = models.DateTimeField(auto_now_add=True)
    public = models.BooleanField(default=True, help_text="Display on site?")

    metadata = models.JSONField(default=dict, blank=True)
    class Meta:
        unique_together = ('summary_type', 'identifier')
        verbose_name_plural = "Summaries"

    def __str__(self):
        return f"{self.summary_type} for {self.identifier}"
    
    def get_html(self) -> str:
        return mark_safe(markdown(self.summary_text))
    
class SummaryPoll(models.Model):
    summary = models.ForeignKey(Summary, on_delete=models.CASCADE)
    vote = models.SmallIntegerField()
    created = models.DateTimeField(auto_now_add=True)
    user_ip = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Poll: {self.vote} for #{self.summary_id}"