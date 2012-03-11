"""This is a half-finished module to track Elections Canada
contribution data.

It and the scraper in parliament.imports.ec were written in summer 2009
and haven't been touched since. Not that they're not worthwhile--they're
just looking for a home, and parents.
"""

from django.db import models

from parliament.elections.models import Candidacy
from parliament.core.models import Person

class Contributor (Person):
    city = models.CharField(max_length=50, blank=True)
    province = models.CharField(max_length=2, blank=True)
    postcode = models.CharField(max_length=7, blank=True)
    
    def __unicode__ (self):
        if self.city and self.province:
            return u"%s (%s, %s)" % (self.name, self.city, self.province)
        else:
            return self.name
    
    def save(self):
        if self.city is None:
            self.city = ''
        if self.province is None:
            self.province = ''
        if len(self.province) > 2:
            self.province = self.province[:2]
        if self.postcode is None:
            self.postcode = ''
        super(Contributor, self).save()
    
class Contribution (models.Model):
    contributor = models.ForeignKey(Contributor)
    amount = models.DecimalField(max_digits=7, decimal_places=2)
    amount_monetary = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)
    amount_nonmonetary = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)
    date = models.DateField(blank=True, null=True)
    individual_recipient = models.ForeignKey(Candidacy)
    
    class Meta:
        ordering = ('-date',)
    
    def __unicode__ (self):
        return u"%s contributed %s to %s (%s) on %s" % (self.contributor.name, self.amount, self.individual_recipient.candidate, self.individual_recipient.party, self.date)
