import datetime

from django.db import models

from parliament.core.models import Politician

class ActiveManager(models.Manager):
    
    def get_query_set(self):
        return super(ActiveManager, self).get_query_set().filter(active=True)

class PoliticianAlert(models.Model):
    
    email = models.EmailField('E-mail')
    politician = models.ForeignKey(Politician)
    active = models.BooleanField(default=False)
    created = models.DateTimeField(default=datetime.datetime.now)
    
    objects = models.Manager()
    public = ActiveManager()