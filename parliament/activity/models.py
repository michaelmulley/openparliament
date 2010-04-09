from django.db import models

from parliament.core.models import Politician

class Activity(models.Model):
    
    date = models.DateField(db_index=True)
    variety = models.CharField(max_length=15)
    politician = models.ForeignKey(Politician)
    payload = models.TextField()
    guid = models.CharField(max_length=50, db_index=True, unique=True)
    
    class Meta:
        ordering = ('-date','-id')
        verbose_name_plural = 'Activities'
        
        