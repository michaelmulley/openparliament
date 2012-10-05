import datetime

from django.db import models


class User(models.Model):

    email = models.EmailField(unique=True, db_index=True)
    email_bouncing = models.BooleanField(default=False)

    created = models.DateTimeField(default=datetime.datetime.now)
    last_login = models.DateTimeField(blank=True, null=True)

    json_data = models.TextField(default='{}')

    def __unicode__(self):
        return self.email

    def log_in(self, request):
        request.authenticated_email = self.email
        self.__class__.objects.filter(id=self.id).update(last_login=datetime.datetime.now())
