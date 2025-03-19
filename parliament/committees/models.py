import datetime
import random
import string

from django.conf import settings
from django.db import models
from django.urls import reverse

from parliament.core.models import Session
from parliament.core.parsetools import slugify
from parliament.core.templatetags.ours import english_list
from parliament.core.utils import memoize_property, language_property
from parliament.hansards.models import Document

class CommitteeManager(models.Manager):

    def get_by_acronym(self, acronym, session):
        try:
            return CommitteeInSession.objects.get(acronym=acronym, session=session).committee
        except CommitteeInSession.DoesNotExist:
            raise Committee.DoesNotExist()

class Committee(models.Model):
    
    name_en = models.TextField()
    short_name_en = models.TextField()
    name_fr = models.TextField(blank=True)
    short_name_fr = models.TextField(blank=True)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey('self', related_name='subcommittees',
        blank=True, null=True, on_delete=models.CASCADE)
    sessions = models.ManyToManyField(Session, through='CommitteeInSession')
    joint = models.BooleanField('Joint committee?', default=False)

    display = models.BooleanField('Display on site?', db_index=True, default=True)

    objects = CommitteeManager()

    name = language_property('name')
    short_name = language_property('short_name')
    
    class Meta:
        ordering = ['name_en']
        
    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.short_name_en:
            self.short_name_en = self.name_en
        if not self.short_name_fr:
            self.short_name_fr = self.name_fr
        if not self.slug:
            self.slug = slugify(self.short_name_en, allow_numbers=True)
            if self.parent:
                self.slug = self.parent.slug + '-' + self.slug
            self.slug = self.slug[:46]
            while Committee.objects.filter(slug=self.slug).exists():
                self.slug += '-' + random.choice(string.lowercase)
        super(Committee, self).save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('committee', kwargs={'slug': self.slug})

    def get_source_url(self):
        return self.committeeinsession_set.order_by('-session__start')[0].get_source_url()

    def get_acronym(self, session):
        if not hasattr(self, '_acronyms'):
            self._acronyms = {}
        if session not in self._acronyms:
            self._acronyms[session] = CommitteeInSession.objects.get(
                committee=self, session=session).acronym
        return self._acronyms[session]

    def latest_session(self):
        return self.sessions.order_by('-start')[0]

    @property
    def title(self):
        if 'committee' in self.name_en.lower():
            return self.name
        else:
            return self.name + ' Committee'

    def to_api_dict(self, representation):
        d = dict(
            name={'en': self.name_en, 'fr': self.name_fr},
            short_name={'en': self.short_name_en, 'fr': self.short_name_fr},
            slug=self.slug,
            parent_url=self.parent.get_absolute_url() if self.parent else None,
        )
        if representation == 'detail':
            d['sessions'] = [{
                    'session': cis.session_id,
                    'acronym': cis.acronym,
                    'source_url': cis.get_source_url(),
                } for cis in self.committeeinsession_set.all().order_by('-session__end').select_related('session')]
            d['subcommittees'] = [c.get_absolute_url() for c in self.subcommittees.all()]
        return d


class CommitteeInSession(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    committee = models.ForeignKey(Committee, on_delete=models.CASCADE)
    acronym = models.CharField(max_length=5, db_index=True)

    class Meta:
        unique_together = [
            ('session', 'committee'),
            ('session', 'acronym'),
        ]

    def __str__(self):
        return "%s (%s) in %s" % (self.committee, self.acronym, self.session_id)

    def get_source_url(self):
        return 'https://www.%(domain)s.ca/Committees/%(lang)s/%(acronym)s?parl=%(parliamentnum)d&session=%(sessnum)d' % {
            'acronym': self.acronym,
            'lang': settings.LANGUAGE_CODE[:2],
            'parliamentnum': self.session.parliamentnum,
            'sessnum': self.session.sessnum,
            'domain': 'parl' if self.committee.joint else 'ourcommons'
        }


class CommitteeActivity(models.Model):
    
    committee = models.ForeignKey(Committee, on_delete=models.CASCADE)

    name_en = models.CharField(max_length=500)
    name_fr = models.CharField(max_length=500)
    
    study = models.BooleanField(default=False) # study or activity

    name = language_property('name')
    
    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('committee_activity', kwargs={'activity_id': self.id})

    def get_source_url(self):
        return self.committeeactivityinsession_set.order_by('-session__start')[0].get_source_url()

    @property
    def type(self):
        return 'Study' if self.study else 'Activity'

    class Meta:
        verbose_name_plural = 'Committee activities'

class CommitteeActivityInSession(models.Model):

    activity = models.ForeignKey(CommitteeActivity, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    source_id = models.IntegerField(unique=True)

    def get_source_url(self):
        return 'https://www.ourcommons.ca/Committees/%(lang)s/%(acronym)s/StudyActivity?studyActivityId=%(source_id)s' % {
            'source_id': self.source_id,
            'acronym': self.activity.committee.get_acronym(self.session),
            'lang': settings.LANGUAGE_CODE[:2]
        }

    class Meta:
        unique_together = [
            ('activity', 'session')
        ]
        
class CommitteeMeeting(models.Model):
    
    date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField(blank=True, null=True)
    source_id = models.IntegerField(blank=True, null=True)
    
    committee = models.ForeignKey(Committee, on_delete=models.CASCADE)
    number = models.SmallIntegerField()
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    
    minutes = models.IntegerField(blank=True, null=True) #docid
    notice = models.IntegerField(blank=True, null=True)
    evidence = models.OneToOneField(Document, blank=True, null=True, on_delete=models.CASCADE)
    
    in_camera = models.BooleanField(default=False)
    travel = models.BooleanField(default=False)
    webcast = models.BooleanField(default=False)
    televised = models.BooleanField(default=False)
    
    activities = models.ManyToManyField(CommitteeActivity)

    class Meta:
        unique_together = [
            ('session', 'committee', 'number')
        ]
    
    def __str__(self):
        return "%s on %s" % (self.committee.short_name, self.date)

    def to_api_dict(self, representation):
        d = dict(
            date=str(self.date),
            number=self.number,
            in_camera=self.in_camera,
            has_evidence=bool(self.evidence_id),
            committee_url=self.committee.get_absolute_url(),
        )
        if representation == 'detail':
            d.update(
                start_time=str(self.start_time),
                end_time=str(self.end_time),
                session=self.session_id,
                minutes_url=self.minutes_url if self.minutes else None,
                notice_url=self.notice_url if self.notice else None,
                webcast_url=self.webcast_url
            )
        return d

    @memoize_property
    def activities_list(self):
        return list(self.activities.all().order_by('-study'))
    
    def activities_summary(self):
        activities = self.activities_list()
        if not activities:
            return None
        if activities[0].study:
            # We have studies, so get rid of the more boring activities
            activities = [a for a in activities if a.study]
        return english_list([a.name_en for a in activities])

    def get_absolute_url(self, pretty=True):
        slug = self.committee.slug if pretty else self.committee_id
        return reverse('committee_meeting',
            kwargs={'session_id': self.session_id, 'committee_slug': slug,
             'number': self.number})

    @property
    def minutes_url(self):
        return self.get_ourcommons_doc_url('minutes') if self.minutes else None

    @property
    def notice_url(self):
        return self.get_ourcommons_doc_url('notice') if self.notice else None

    @property
    def evidence_url(self):
        return self.get_ourcommons_doc_url('evidence') if self.evidence_id else None

    def get_ourcommons_doc_url(self, document_type, lang=settings.LANGUAGE_CODE[:2]):
        domain = 'parl' if self.committee.joint else 'ourcommons'
        acro = self.committee.get_acronym(self.session)
        return f'https://www.{domain}.ca/DocumentViewer/{lang}/{self.session.id}/{acro}/meeting-{self.number}/{document_type}'
    
    @property
    def webcast_url(self):
        if not self.webcast:
            return None
        return 'https://www.ourcommons.ca/webcast/{}/{}/{}'.format(
            self.session.id, self.committee.get_acronym(self.session), self.number)
    
    @property
    def datetime(self):
        return datetime.datetime.combine(self.date, self.start_time)

    @property
    def future(self):
        return self.datetime > datetime.datetime.now()

class CommitteeReport(models.Model):
    
    committee = models.ForeignKey(Committee, on_delete=models.CASCADE)
    
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    number = models.SmallIntegerField(blank=True, null=True) # watch this become a char
    name_en = models.CharField(max_length=500)
    name_fr = models.CharField(max_length=500, blank=True)
    
    source_id = models.IntegerField(unique=True, db_index=True)
    
    adopted_date = models.DateField(blank=True, null=True)
    presented_date = models.DateField(blank=True, null=True)
    
    government_response = models.BooleanField(default=False)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children', on_delete=models.CASCADE)

    name = language_property('name')
    
    def __str__(self):
        return "%s report #%s" % (self.committee, self.number)
