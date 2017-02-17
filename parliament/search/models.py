import datetime

from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models

class IndexingTask(models.Model):

    action = models.CharField(max_length=10)
    identifier = models.CharField(max_length=100)

    timestamp = models.DateTimeField(default=datetime.datetime.now)

    content_type = models.ForeignKey(ContentType, null=True, blank=True)
    object_id = models.CharField(max_length=20, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    def __unicode__(self):
        return u'%s %s' % (self.action, self.identifier)
