import datetime
import hashlib
import base64

from django.db import models
from django.conf import settings
from django.utils.translation import ugettext as _

from parliament.core.models import Politician
from parliament.core.utils import ActiveManager


class PoliticianAlert(models.Model):
    email = models.EmailField('Your e-mail')
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
        return base64.urlsafe_b64encode(h.digest()).replace('=', '')

    @models.permalink
    def get_unsubscribe_url(self):
        return (
            'parliament.alerts.views.unsubscribe',
            [],
            {'alert_id': self.id, 'key': self.get_key()}
        )

    def __unicode__(self):
        return _(u"%(email)s for %(politician)s (%(active)s)") % {
            email: self.email,
            politician: self.politician.name,
            active: 'active' if self.active else 'inactive'
        }
