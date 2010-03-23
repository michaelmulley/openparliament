import gzip, sys, os

from django.db import models
from django.conf import settings

from parliament.core.models import Session, ElectedMember
from parliament.core import parsetools

class HansardManager (models.Manager):
    
    def establishSequence(self):
        seq = 0
        for h in self.get_query_set().filter(date__isnull=False).order_by('date'):
            h.sequence = seq
            h.save()
            seq += 1
            
class Hansard(models.Model):
    date = models.DateField(blank=True, null=True)
    #number = models.IntegerField(blank=True, null=True) # apparently there exist 'numbers' with letters
    number = models.CharField(max_length=6, blank=True)
    url = models.URLField(verify_exists=False)
    session = models.ForeignKey(Session)
    sequence = models.IntegerField(blank=True, null=True)
    
    objects = HansardManager()
    
    def __unicode__ (self):
        return u"Hansard #%s for %s" % (self.number, self.date)
        
    @models.permalink
    def get_absolute_url(self):
        return ('parliament.hansards.views.hansard', [self.id])


class HansardCache(models.Model):
    hansard = models.ForeignKey(Hansard)
    filename = models.CharField(max_length=100)
    
    def makeFilename(self):
        return '%d_%d_%s.html.gz' % (self.hansard.session.parliamentnum, self.hansard.session.sessnum, self.hansard.number)
    
    def makeFilepath(self, filename):
        return settings.HANSARD_CACHE_DIR + filename
    
    def saveHTML(self, html):
        if self.filename:
            return False
        filename = self.makeFilename()
        path = self.makeFilepath(filename)
        if os.path.exists(path):
            raise Exception("Already a file at %s" % path)
        out = gzip.open(path, 'wb')
        out.write(html)
        out.close()
        self.filename = filename
        self.save()
        return True
        
    def getHTML(self):
        infile = gzip.open(self.makeFilepath(self.filename), 'rb')
        html = infile.read()
        infile.close()
        return html
        
class Statement(models.Model):
    hansard = models.ForeignKey(Hansard)
    time = models.DateTimeField(blank=True, null=True)
    heading = models.CharField(max_length=110, blank=True)
    topic = models.CharField(max_length=200, blank=True)
    member = models.ForeignKey(ElectedMember, blank=True, null=True)
    who = models.CharField(max_length=300)
    text = models.TextField()
    sequence = models.IntegerField()
    wordcount = models.IntegerField()
        
    class Meta:
        ordering = ('sequence',)
        
    def save(self, *args, **kwargs):
        if self.heading is None:
            self.heading = ''
        if self.topic is None:
            self.topic = ''
        if not self.wordcount:
            self.wordcount = parsetools.countWords(self.text)
        super(Statement, self).save(*args, **kwargs)
        
    def get_absolute_url(self):
        return self.hansard.get_absolute_url() + "#s%d" % self.sequence
    
    def __unicode__ (self):
        return u"%s speaking about %s around %s on %s" % (self.who, self.topic, self.time, self.hansard.date)
