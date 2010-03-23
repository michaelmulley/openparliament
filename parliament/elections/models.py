from django.db import models

from parliament.core.models import Politician, Riding, Party

class Election (models.Model):
    date = models.DateField()
    byelection = models.BooleanField()
    
    class Meta:
        ordering = ('-date',)
    
    def __unicode__ (self):
        if self.byelection:
            return u"Byelection of %s" % self.date
        else:
            return u"General election of %s" % self.date

class Candidacy (models.Model):
    candidate = models.ForeignKey(Politician)
    riding = models.ForeignKey(Riding)
    party = models.ForeignKey(Party)
    election = models.ForeignKey(Election)
    occupation = models.CharField(max_length=100, blank=True)
    votetotal = models.IntegerField(blank=True, null=True)
    elected = models.NullBooleanField(blank=True, null=True)
    
    class Meta:
        verbose_name_plural = 'Candidacies'
    
    def __unicode__ (self):
        return u"%s (%s) was a candidate in %s in the %s" % (self.candidate, self.party, self.riding, self.election)
