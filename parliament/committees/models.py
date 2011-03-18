from django.db import models

from parliament.core.models import Session
from parliament.hansards.models import Document

class Committee(models.Model):
    
    name = models.TextField()
    acronym = models.CharField(max_length=4, db_index=True)
    parent = models.ForeignKey('self', related_name='subcommittees',
        blank=True, null=True)
    active = models.BooleanField()
    sessions = models.ManyToManyField(Session)
    
    class Meta:
        ordering = ['name']
        
    def __unicode__(self):
        return u"%s (%s)" % (self.name, self.acronym)
    
    @models.permalink
    def get_absolute_url(self):
        if self.active:
            return ('parliament.committees.views.committee', [],
            {'acronym': self.acronym})
        else:
            return ('parliament.committees.views.committee', [],
            {'committee_id': self.id})
        
class CommitteeActivity(models.Model):
    
    source_id = models.IntegerField()
    
    name_en = models.CharField(max_length=500)
    name_fr = models.CharField(max_length=500)
    
    study = models.BooleanField(default=False) # study or activity
        
class CommitteeMeeting(models.Model):
    
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    committee = models.ForeignKey(Committee)
    number = models.SmallIntegerField()
    session = models.ForeignKey(Session)
    
    minutes = models.IntegerField(blank=True, null=True) #docid
    notice = models.IntegerField(blank=True, null=True)
    evidence = models.OneToOneField(Document, blank=True, null=True)
    
    in_camera = models.BooleanField(default=False)
    travel = models.BooleanField(default=False)
    webcast = models.BooleanField(default=False)
    televised = models.BooleanField(default=False)
    
    activities = models.ManyToManyField(CommitteeActivity)

class CommitteeReport(models.Model):
    
    committee = models.ForeignKey(Committee)
    
    number = models.SmallIntegerField(blank=True, null=True) # watch this become a char
    name = models.CharField(max_length=500)
    
    source_id = models.IntegerField()
    
    adopted_date = models.DateField(blank=True, null=True)
    presented_date = models.DateField(blank=True, null=True)
