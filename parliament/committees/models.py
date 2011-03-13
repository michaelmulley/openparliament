from django.db import models

from parliament.core.models import Session

class Committee(models.Model):
    
    name = models.TextField()
    acronym = models.CharField(max_length=4, db_index=True)
    parent = models.ForeignKey('self', related_name='subcommittees',
        blank=True, null=True)
    active = models.BooleanField()
    sessions = models.ManyToManyField(Session)
    
    def __unicode__(self):
        return u"%s (%s)" % (self.name, self.acronym)