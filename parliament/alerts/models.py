import datetime
import hashlib
import base64

from django.db import models
from django.conf import settings

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
    
    def get_key(self):
        h = hashlib.sha1()
        h.update(str(self.id))
        h.update(self.email)
        h.update(settings.SECRET_KEY)
        return base64.urlsafe_b64encode(h.digest())
        
    @models.permalink
    def get_unsubscribe_url(self):
        return ('parliament.alerts.views.unsubscribe', [], {'alert_id': self.id, 'key': self.get_key()})