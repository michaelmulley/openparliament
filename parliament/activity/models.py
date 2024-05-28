from django.db import models

from parliament.core.models import Politician
from parliament.core.utils import ActiveManager

class Activity(models.Model):
    
    date = models.DateField(db_index=True)
    variety = models.CharField(max_length=15)
    politician = models.ForeignKey(Politician, on_delete=models.CASCADE)
    payload = models.TextField()
    guid = models.CharField(max_length=50, db_index=True, unique=True)
    active = models.BooleanField(default=True, db_index=True)
    
    objects = models.Manager()
    public = ActiveManager()
    
    class Meta:
        ordering = ('-date','-id')
        verbose_name_plural = 'Activities'
        
    def payload_wrapped(self):
        return '<p class="activity_item" data-id="%s">%s</p>' % (self.pk, self.payload)

    def save(self, *args, **kwargs):
        self.full_clean()
        super(Activity, self).save(*args, **kwargs)
        
        