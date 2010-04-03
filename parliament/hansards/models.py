import gzip, sys, os, re

from django.db import models
from django.conf import settings
from django.core import urlresolvers
from django.contrib.markup.templatetags.markup import markdown
from django.utils.html import strip_tags, escape
from django.utils.safestring import mark_safe

from parliament.core.models import Session, ElectedMember, Politician
from parliament.bills.models import Bill
from parliament.core import parsetools
from parliament.core.utils import simple_function_cache

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
    
    class Meta:
        ordering = ('-date',)
    
    def __unicode__ (self):
        return u"Hansard #%s for %s" % (self.number, self.date)
        
    @models.permalink
    def get_absolute_url(self):
        return ('parliament.hansards.views.hansard', [self.id])
        
    def topics(self):
        """Returns a tuple with (topic, statement sequence ID) for every topic mentioned."""
        topics = []
        last_topic = ''
        for statement in self.statement_set.all().values_list('topic', 'sequence'):
            if statement[0] != last_topic:
                last_topic = statement[0]
                topics.append((statement[0], statement[1]))
        return topics

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
        
r_statement_affil = re.compile(r'<(bill|pol) id="(\d+)" name="(.+?)">(.+?)</\1>', re.UNICODE)
def statement_affil_link(match):
    if match.group(1) == 'bill':
        # FIXME hardcode url for speed?
        view = 'parliament.bills.views.bill'
    else:
        view = 'parliament.politicians.views.politician'
    return '<a href="%s" class="related_link" title="%s">%s</a>' % (urlresolvers.reverse(view, args=(match.group(2),)), match.group(3), match.group(4))
    
class Statement(models.Model):
    hansard = models.ForeignKey(Hansard)
    time = models.DateTimeField(blank=True, null=True, db_index=True)
    heading = models.CharField(max_length=110, blank=True)
    topic = models.CharField(max_length=200, blank=True)
    member = models.ForeignKey(ElectedMember, blank=True, null=True)
    politician = models.ForeignKey(Politician, blank=True, null=True) # a shortcut -- should == member.politician
    who = models.CharField(max_length=300)
    text = models.TextField()
    sequence = models.IntegerField(db_index=True)
    wordcount = models.IntegerField()
    
    bills = models.ManyToManyField(Bill, blank=True)
        
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
        
    def save_relationships(self):
        bill_ids = set()
        for match in r_statement_affil.finditer(self.text):
            if match.group(1) == 'bill':
                bill_ids.add(match.group(2))
        if bill_ids:
            self.bills.add(*list(bill_ids))
    
    @models.permalink
    def get_absolute_url(self):
        return ('parliament.hansards.views.hansard', [], {'hansard_id': self.hansard_id, 'statement_seq': self.sequence})
    
    def __unicode__ (self):
        return u"%s speaking about %s around %s on %s" % (self.who, self.topic, self.time, self.hansard.date)
        
    def text_html(self):
        return mark_safe(markdown(r_statement_affil.sub(statement_affil_link, self.text)))

    def text_plain(self):
        return escape(strip_tags(self.text).replace('> ', ''))
    
    @property
    @simple_function_cache    
    def name_info(self):
        info = {
            'post': None,
            'named': True
        }
        if not self.member:
            info['display_name'] = parsetools.r_mister.sub('', self.who)
        elif parsetools.r_notamember.search(self.who):
            info['display_name'] = self.who
            if self.member.politician.name in self.who:
                info['display_name'] = re.sub(r'\(.+?\)', '', self.who)
            info['named'] = False
        elif not '(' in self.who or not parsetools.r_politicalpost.search(self.who):
            info['display_name'] = self.member.politician.name
        else:
            info['post'] = post = re.search(r'\((.+)\)', self.who).group(1).split(',')[0]
            info['display_name'] = self.member.politician.name
        return info
    
    def normalized_who(self):
        if not self.member:
            return parsetools.r_mister.sub('', self.who)
        riding = self.member.riding.dashed_name
        party = self.member.party.short_name
        #if self.member.party.colour:
        #    party = '<span class="tag" style="background-color: %s">%s</span>' % (self.member.party.colour, party)
        if parsetools.r_notamember.search(self.who):
            polname = self.who
            affil = ''
            title = '%s (%s, %s)' % (self.who, riding, party)
        elif not '(' in self.who or not parsetools.r_politicalpost.search(self.who):
            polname = self.member.politician.name
            affil = '(%s, %s)' % (riding, party)
            title = ''
        else:
            # We have a political post
            post = re.search(r'\((.+)\)', self.who).group(1).split(',')[0]
            polname = self.member.politician.name
            affil = '(%s, %s)' % (post, party)
            title = 'MP for %s' % riding
        return mark_safe('<a href="%s" title="%s">%s</a> <span class="pol_affil">%s</a>' %
            (self.member.politician.get_absolute_url(), title, polname, affil))
            
