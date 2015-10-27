from decimal import Decimal
from collections import defaultdict

from django.db import models

from parliament.core.models import Politician, Riding, Party, ElectedMember

import logging
logger = logging.getLogger(__name__)

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
                
    def label_winners(self):
        """Sets the elected boolean on this election's Candidacies"""
        candidacies = self.candidacy_set.all()
        candidacies.update(elected=None)
        riding_candidacies = defaultdict(list)
        for candidacy in candidacies:
            riding_candidacies[candidacy.riding_id].append(candidacy)
        for riding_candidacies in riding_candidacies.values():
            winner = max(riding_candidacies, key=lambda c: c.votetotal)
            winner.elected = True
            winner.save()
        candidacies.filter(elected=None).update(elected=False)
        
    def create_members(self, session):
        for candidacy in self.candidacy_set.filter(elected=True):
            candidacy.create_member(session)
                
class CandidacyManager(models.Manager):
    
    def create_from_name(self, first_name, last_name, riding, party, election,
            votetotal, elected, votepercent=None, occupation='', interactive=True):
        """Create a Candidacy based on a candidate's name; checks for prior
        Politicians representing the same person.
        
        first_name and last_name are strings; remaining arguments are as in
        the Candidacy model"""
        
        candidate = None
        fullname = u' '.join((first_name, last_name))
        candidates = Politician.objects.filter_by_name(fullname)
        # If there's nothing in the list, try a little harder
        if not candidates:
            # Does the candidate have many given names?
            if first_name.strip().count(' ') >= 1:
                minifirst = first_name.strip().split(' ')[0]
                candidates = Politician.objects.filter_by_name("%s %s" % (minifirst, last_name))
        # Then, evaluate the possibilities in the list
        for posscand in candidates:
            # You're only a match if you've run for office for the same party in the same province
            match = (
                ElectedMember.objects.filter(riding__province=riding.province, party=party, politician=posscand).exists()
                or Candidacy.objects.filter(riding__province=riding.province, party=party, candidate=posscand).exists())
            if match:
                if candidate is not None:
                    if interactive:
                        print "Please enter Politician ID for %r (%r)" % (fullname, riding.name)
                        candidate = Politician.objects.get(pk=raw_input().strip())
                        break
                    else:
                        raise Politician.MultipleObjectsReturned(
                            "Could not disambiguate among existing candidates for %s" % fullname)
                candidate = posscand
                    
        if candidate is None:
            candidate = Politician(name=fullname, name_given=first_name, name_family=last_name)
            candidate.save()
            
        return self.create(
            candidate=candidate,
            riding=riding,
            party=party,
            election=election,
            votetotal=votetotal,
            elected=elected,
            votepercent=votepercent,
            occupation=occupation
        )
        

class Candidacy (models.Model):
    candidate = models.ForeignKey(Politician)
    riding = models.ForeignKey(Riding)
    party = models.ForeignKey(Party)
    election = models.ForeignKey(Election)
    occupation = models.CharField(max_length=100, blank=True)
    votetotal = models.IntegerField(blank=True, null=True)
    votepercent = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    elected = models.NullBooleanField(blank=True, null=True)
    
    objects = CandidacyManager()
    
    class Meta:
        verbose_name_plural = 'Candidacies'
        
    def create_member(self, session=None):
        """Creates an ElectedMember for a winning candidate"""
        if not self.elected:
            return False
        try:
            member = ElectedMember.objects\
                .filter(models.Q(end_date__isnull=True) | models.Q(end_date=self.election.date))\
                .get(politician=self.candidate,
                riding=self.riding,
                party=self.party)
            member.end_date = None
            member.save()
        except ElectedMember.DoesNotExist:
            member = ElectedMember.objects.create(
                politician=self.candidate,
                riding=self.riding,
                party=self.party,
                start_date=self.election.date
            )
        if session:
            member.sessions.add(session)
        if not self.candidate.slug:
            self.candidate.add_slug()
        return member
    
    def __unicode__ (self):
        return u"%s (%s) was a candidate in %s in the %s" % (self.candidate, self.party, self.riding, self.election)
