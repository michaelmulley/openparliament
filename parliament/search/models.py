import datetime

from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models

class IndexingTask(models.Model):

    action = models.CharField(max_length=10)
    identifier = models.CharField(max_length=100)

    timestamp = models.DateTimeField(default=datetime.datetime.now)

    content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=20, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    def __str__(self):
        return '%s %s' % (self.action, self.identifier)
