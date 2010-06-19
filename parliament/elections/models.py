from decimal import Decimal
from collections import defaultdict

from django.db import models

from parliament.core.models import Politician, Riding, Party

class Election (models.Model):
    date = models.DateField(db_index=True)
    byelection = models.BooleanField()
    
    class Meta:
        ordering = ('-date',)
    
    def __unicode__ (self):
        if self.byelection:
            return u"Byelection of %s" % self.date
        else:
            return u"General election of %s" % self.date
    
    def calculate_vote_percentages(self):
        candidacies = self.candidacy_set.all()
        riding_candidacies = defaultdict(list)
        riding_votetotals = defaultdict(Decimal)
        for candidacy in candidacies:
            riding_candidacies[candidacy.riding_id].append(candidacy)
            riding_votetotals[candidacy.riding_id] += candidacy.votetotal
        for riding in riding_candidacies:
            for candidacy in riding_candidacies[riding]:
                candidacy.votepercent = (Decimal(candidacy.votetotal) / riding_votetotals[riding]) * 100
                candidacy.save()

class Candidacy (models.Model):
    candidate = models.ForeignKey(Politician)
    riding = models.ForeignKey(Riding)
    party = models.ForeignKey(Party)
    election = models.ForeignKey(Election)
    occupation = models.CharField(max_length=100, blank=True)
    votetotal = models.IntegerField(blank=True, null=True)
    votepercent = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    elected = models.NullBooleanField(blank=True, null=True)
    
    class Meta:
        verbose_name_plural = 'Candidacies'
    
    def __unicode__ (self):
        return u"%s (%s) was a candidate in %s in the %s" % (self.candidate, self.party, self.riding, self.election)
