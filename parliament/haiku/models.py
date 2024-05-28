import re

from django.core.exceptions import ValidationError
from django.db import models
from django.template import defaultfilters

from parliament.hansards.models import Statement

def validate_first_line(line):
    if not re.search(r'^[A-Z]', line):
        raise ValidationError("Doesn't start with cap")
        
def validate_last_line(line):
    if re.search(r'(Mr|St|Mrs|No|Hon)\.$', line, re.I):
        raise ValidationError("Ends with non-period")
    if line.endswith(':') or line.endswith('-'):
        raise ValidationError("Colon")
        
def validate_line(line):
    if re.search(r'\d', line):
        raise ValidationError("Digits")
    if '[' in line:
        raise ValidationError("Brackets")
    if u'—' in line or '--' in line:
        raise ValidationError("Dash")

class Haiku(models.Model):
    line1 = models.CharField(max_length=50,
        validators=[validate_first_line, validate_line])
    line2 = models.CharField(max_length=70,
        validators=[validate_line])
    line3 = models.CharField(max_length=50,
        validators=[validate_last_line, validate_line])
    
    attribution = models.CharField(max_length=300)
    attribution_url = models.CharField(max_length=100)
    worthy = models.BooleanField(blank=True, default=False, db_index=True)
    #statement = models.ForeignKey(Statement)
    
    def set_statement(self, statement):
        self.attribution_url = statement.get_absolute_url()
        if statement.member:
            a = "%s MP %s" % (statement.member.party.short_name, statement.politician.name)
        else:
            a = statement.name_info['display_name']
        a += ' in ' + defaultfilters.date(statement.time, "F Y")
        self.attribution = a
    
    def __str__(self):
        return '%s / %s / %s' % (self.line1, self.line2, self.line3)
        
    class Meta:
        db_table = 'labs_haiku'