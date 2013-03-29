import datetime
import random
import string

from django.conf import settings
from django.db import models

from parliament.core.models import Session
from parliament.core.parsetools import slugify
from parliament.core.templatetags.ours import english_list
from parliament.core.utils import memoize_property
from parliament.hansards.models import Document, url_from_docid

class CommitteeManager(models.Manager):

    def get_by_acronym(self, acronym, session):
        try:
            return CommitteeInSession.objects.get(acronym=acronym, session=session).committee
        except CommitteeInSession.DoesNotExist:
            raise Committee.DoesNotExist()

class Committee(models.Model):
    
    name = models.TextField()
    short_name = models.TextField()
    name_fr = models.TextField(null=True, blank=True)
    short_name_fr = models.TextField(null=True, blank=True)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey('self', related_name='subcommittees',
        blank=True, null=True)
    sessions = models.ManyToManyField(Session, through='CommitteeInSession')

    display = models.BooleanField('Display on site?', db_index=True, default=True)

    objects = CommitteeManager()
    
    class Meta:
        ordering = ['name']
        
    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.short_name:
            self.short_name = self.name
        if not self.slug:
            self.slug = slugify(self.short_name, allow_numbers=True)
            if self.parent:
                self.slug = self.parent.slug + '-' + self.slug
            self.slug = self.slug[:46]
            while Committee.objects.filter(slug=self.slug).exists():
                self.slug += '-' + random.choice(string.lowercase)
        super(Committee, self).save(*args, **kwargs)
    
    @models.permalink
    def get_absolute_url(self):
        return ('parliament.committees.views.committee', [],
            {'slug': self.slug})

    def get_source_url(self):
        return self.committeeinsession_set.order_by('-session__start')[0].get_source_url()

    def get_acronym(self, session):
        return CommitteeInSession.objects.get(
            committee=self, session=session).acronym

    def latest_session(self):
        return self.sessions.order_by('-start')[0]

    @property
    def title(self):
        if 'committee' in self.name.lower():
            return self.name
        else:
            return self.name + u' Committee'

class CommitteeInSession(models.Model):
    session = models.ForeignKey(Session)
    committee = models.ForeignKey(Committee)
    acronym = models.CharField(max_length=5, db_index=True)

    class Meta:
        unique_together = [
            ('session', 'committee'),
            ('session', 'acronym'),
        ]

    def __unicode__(self):
        return u"%s (%s) in %s" % (self.committee, self.acronym, self.session_id)

    def get_source_url(self):
        return 'http://parl.gc.ca/CommitteeBusiness/CommitteeHome.aspx?Cmte=%(acronym)s&Language=%(lang)s&Mode=1&Parl=%(parliamentnum)s&Ses=%(sessnum)s' % {
            'acronym': self.acronym,
            'lang': settings.LANGUAGE_CODE.upper()[0],
            'parliamentnum': self.session.parliamentnum,
            'sessnum': self.session.sessnum
        }


class CommitteeActivity(models.Model):
    
    committee = models.ForeignKey(Committee)

    name_en = models.CharField(max_length=500)
    name_fr = models.CharField(max_length=500)
    
    study = models.BooleanField(default=False) # study or activity
    
    def __unicode__(self):
        return self.name_en

    @models.permalink
    def get_absolute_url(self):
        return ('committee_activity', [], {'activity_id': self.id})

    def get_source_url(self):
        return self.committeeactivityinsession_set.order_by('-session__start')[0].get_source_url()

    @property
    def type(self):
        return 'Study' if self.study else 'Activity'

    class Meta:
        verbose_name_plural = 'Committee activities'

class CommitteeActivityInSession(models.Model):

    activity = models.ForeignKey(CommitteeActivity)
    session = models.ForeignKey(Session)
    source_id = models.IntegerField(unique=True)

    def get_source_url(self):
        return 'http://www.parl.gc.ca/CommitteeBusiness/StudyActivityHome.aspx?Stac=%(source_id)d&Parl=%(parliamentnum)d&Ses=%(sessnum)d' % {
            'source_id': self.source_id,
            'parliamentnum': self.session.parliamentnum,
            'sessnum': self.session.sessnum
        }

    class Meta:
        unique_together = [
            ('activity', 'session')
        ]
        
class CommitteeMeeting(models.Model):
    
    date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField(blank=True, null=True)
    
    committee = models.ForeignKey(Committee)
    number = models.SmallIntegerField()
    session = models.ForeignKey(Session)
    
    minutes = models.IntegerField(blank=True, null=True) #docid
    notice = models.IntegerField(blank=True, null=True)
    evidence = models.OneToOneField(Document, blank=True, null=True)
    
    in_camera = models.BooleanField(default=False)
    travel = models.BooleanField(default=False)
    webcast = models.BooleanField(default=False)
    televised = models.BooleanField(default=False)
    
    activities = models.ManyToManyField(CommitteeActivity)

    class Meta:
        unique_together = [
            ('session', 'committee', 'number')
        ]
    
    def __unicode__(self):
        return u"%s on %s" % (self.committee.short_name, self.date)

    @memoize_property
    def activities_list(self):
        return list(self.activities.all().order_by('-study'))
    
    def activities_summary(self):
        activities = self.activities_list()
        if not activities:
            return None
        if activities[0].study:
            # We have studies, so get rid of the more boring activities
            activities = filter(lambda a: a.study, activities)
        return english_list(map(lambda a: a.name_en, activities))

    @models.permalink
    def get_absolute_url(self, pretty=True):
        slug = self.committee.slug if pretty else self.committee_id
        return ('committee_meeting', [],
            {'session_id': self.session_id, 'committee_slug': slug,
             'number': self.number})

    @property
    def minutes_url(self):
        return url_from_docid(self.minutes)

    @property
    def notice_url(self):
        return url_from_docid(self.notice)

    @property
    def webcast_url(self):
        return 'http://www.parl.gc.ca/CommitteeBusiness/CommitteeMeetings.aspx?Cmte=%(acronym)s&Mode=1&ControlCallback=pvuWebcast&Parl=%(parliamentnum)d&Ses=%(sessnum)d&Organization=%(acronym)s&MeetingNumber=%(meeting_number)d&Language=%(language)s&NoJavaScript=true' % {
            'acronym': self.committee.get_acronym(self.session),
            'parliamentnum': self.session.parliamentnum,
            'sessnum': self.session.sessnum,
            'meeting_number': self.number,
            'language': settings.LANGUAGE_CODE[0].upper()
        } if self.webcast else None

    @property
    def datetime(self):
        return datetime.datetime.combine(self.date, self.start_time)

    @property
    def future(self):
        return self.datetime > datetime.datetime.now()

class CommitteeReport(models.Model):
    
    committee = models.ForeignKey(Committee)
    
    session = models.ForeignKey(Session)
    number = models.SmallIntegerField(blank=True, null=True) # watch this become a char
    name = models.CharField(max_length=500)
    
    source_id = models.IntegerField(unique=True, db_index=True)
    
    adopted_date = models.DateField(blank=True, null=True)
    presented_date = models.DateField(blank=True, null=True)
    
    government_response = models.BooleanField(default=False)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')
    
    def __unicode__(self):
        return u"%s report #%s" % (self.committee, self.number)
