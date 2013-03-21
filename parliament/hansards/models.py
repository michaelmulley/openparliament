#coding: utf-8

import gzip, os, re
from collections import defaultdict
import datetime

from django.db import models
from django.conf import settings
from django.core import urlresolvers
from django.core.files.base import ContentFile
from django.template.defaultfilters import slugify
from django.utils.datastructures import SortedDict
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

from parliament.core.models import Session, ElectedMember, Politician
from parliament.bills.models import Bill
from parliament.core import parsetools, text_utils
from parliament.core.utils import memoize_property
from parliament.activity import utils as activity

import logging
logger = logging.getLogger(__name__)

class DebateManager(models.Manager):

    def get_query_set(self):
        return super(DebateManager, self).get_query_set().filter(document_type=Document.DEBATE)

class EvidenceManager(models.Manager):

    def get_query_set(self):
        return super(EvidenceManager, self).get_query_set().filter(document_type=Document.EVIDENCE)

class NoStatementManager(models.Manager):
    """Manager restricts to Documents that haven't had statements parsed."""

    def get_query_set(self):
        return super(NoStatementManager, self).get_query_set()\
            .annotate(scount=models.Count('statement'))\
            .exclude(scount__gt=0)

def url_from_docid(docid):
    return "http://www.parl.gc.ca/HousePublications/Publication.aspx?DocId=%s&Language=%s&Mode=1" % (
        docid, settings.LANGUAGE_CODE[0].upper()
    ) if docid else None

class Document(models.Model):
    
    DEBATE = 'D'
    EVIDENCE = 'E'
    
    document_type = models.CharField(max_length=1, db_index=True, choices=(
        ('D', 'Debate'),
        ('E', 'Committee Evidence'),
    ))
    date = models.DateField(blank=True, null=True)
    number = models.CharField(max_length=6, blank=True) # there exist 'numbers' with letters
    session = models.ForeignKey(Session)
    
    source_id = models.IntegerField(unique=True, db_index=True)
    
    most_frequent_word = models.CharField(max_length=20, blank=True)
    wordcloud = models.ImageField(upload_to='autoimg/wordcloud', blank=True, null=True)

    downloaded = models.BooleanField(default=False,
        help_text="Has the source data been downloaded?")
    skip_parsing = models.BooleanField(default=False,
        help_text="Don't try to parse this, presumably because of errors in the source.")

    public = models.BooleanField("Display on site?", default=False)
    multilingual = models.BooleanField("Content parsed in both languages?", default=False)

    objects = models.Manager()
    debates = DebateManager()
    evidence = EvidenceManager()
    without_statements = NoStatementManager()
    
    class Meta:
        ordering = ('-date',)
    
    def __unicode__ (self):
        if self.document_type == self.DEBATE:
            return u"Hansard #%s for %s (#%s/#%s)" % (self.number, self.date, self.id, self.source_id)
        else:
            return u"%s evidence for %s (#%s/#%s)" % (
                self.committeemeeting.committee.short_name, self.date, self.id, self.source_id)
        
    @memoize_property
    def get_absolute_url(self):
        if self.document_type == self.DEBATE:
            return urlresolvers.reverse('debate', kwargs={
                'year': self.date.year, 'month': self.date.month, 'day': self.date.day
            })
        elif self.document_type == self.EVIDENCE:
            return self.committeemeeting.get_absolute_url()

    def to_api_dict(self, representation):
        d = dict(
            date=unicode(self.date) if self.date else None,
            number=self.number,
            most_frequent_word=self.most_frequent_word,
        )
        if representation == 'detail':
            d.update(
                source_id=self.source_id,
                source_url=self.source_url,
                session=self.session_id,
                document_type=self.get_document_type_display(),
            )
        return d

    @property
    def url(self):
        return self.source_url

    @property
    def source_url(self):
        return url_from_docid(self.source_id)
        
    def _topics(self, l):
        topics = []
        last_topic = ''
        for statement in l:
            if statement[0] and statement[0] != last_topic:
                last_topic = statement[0]
                topics.append((statement[0], statement[1]))
        return topics
        
    def topics(self):
        """Returns a tuple with (topic, statement slug) for every topic mentioned."""
        return self._topics(self.statement_set.all().values_list('h2', 'slug'))
        
    def headings(self):
        """Returns a tuple with (heading, statement slug) for every heading mentioned."""
        return self._topics(self.statement_set.all().values_list('h1', 'slug'))
    
    def topics_with_qp(self):
        """Returns the same as topics(), but with a link to Question Period at the start of the list."""
        statements = self.statement_set.all().values_list('h2', 'slug', 'h1')
        topics = self._topics(statements)
        qp_seq = None
        for s in statements:
            if s[2] == 'Oral Questions':
                qp_seq = s[1]
                break
        if qp_seq is not None:
            topics.insert(0, ('Question Period', qp_seq))
        return topics

    @memoize_property
    def speaker_summary(self):
        """Returns a sorted dictionary (in order of appearance) summarizing the people
        speaking in this document.

        Keys are names, suitable for displays. Values are dicts with keys:
            slug: Slug of first statement by the person
            politician: Boolean -- is this an MP?
            description: Short title or affiliation
        """
        ids_seen = set()
        speakers = SortedDict()
        for st in self.statement_set.filter(who_hocid__isnull=False).values(
                'who', 'who_context', 'slug', 'politician__name', 'who_hocid'):
            if st['who_hocid'] in ids_seen:
                continue
            ids_seen.add(st['who_hocid'])
            if st['politician__name']:
                who = st['politician__name']
            else:
                who = parsetools.r_parens.sub('', st['who'])
                who = re.sub('^\s*\S+\s+', '', who).strip() # strip honorific
            if who not in speakers:
                info = {
                    'slug': st['slug'],
                    'politician': bool(st['politician__name'])
                }
                if st['who_context']:
                    info['description'] = st['who_context']
                speakers[who] = info
        return speakers

    def outside_speaker_summary(self):
        """Same as speaker_summary, but only non-MPs."""
        return SortedDict(
            [(k, v) for k, v in self.speaker_summary().items() if not v['politician']]
        )

    def mp_speaker_summary(self):
        """Same as speaker_summary, but only MPs."""
        return SortedDict(
            [(k, v) for k, v in self.speaker_summary().items() if v['politician']]
        )
    
    def save_activity(self):
        statements = self.statement_set.filter(procedural=False).select_related('member', 'politician')
        politicians = set([s.politician for s in statements if s.politician])
        for pol in politicians:
            topics = {}
            wordcount = 0
            for statement in filter(lambda s: s.politician == pol, statements):
                wordcount += statement.wordcount
                if statement.topic in topics:
                    # If our statement is longer than the previous statement on this topic,
                    # use its text for the excerpt.
                    if len(statement.text_plain()) > len(topics[statement.topic][1]):
                        topics[statement.topic][1] = statement.text_plain()
                        topics[statement.topic][2] = statement.get_absolute_url()
                else:
                    topics[statement.topic] = [statement.slug, statement.text_plain(), statement.get_absolute_url()]
            for topic in topics:
                if self.document_type == Document.DEBATE:
                    activity.save_activity({
                        'topic': topic,
                        'url': topics[topic][2],
                        'text': topics[topic][1],
                    }, politician=pol, date=self.date, guid='statement_%s' % topics[topic][2], variety='statement')
                elif self.document_type == Document.EVIDENCE:
                    assert len(topics) == 1
                    if wordcount < 80:
                        continue
                    (seq, text, url) = topics.values()[0]
                    activity.save_activity({
                        'meeting': self.committeemeeting,
                        'committee': self.committeemeeting.committee,
                        'text': text,
                        'url': url,
                        'wordcount': wordcount,
                    }, politician=pol, date=self.date, guid='cmte_%s' % url, variety='committee')
                
    def serializable(self):
        return {
            'date': self.date,
            'url': self.get_absolute_url(),
            'id': self.id,
            'original_url': self.url,
            'parliament': self.session.parliamentnum,
            'session': self.session.sessnum,
            'statements': [s.serializable()
                for s in self.statement_set.all()
                    .order_by('sequence')
                    .select_related('member__politician', 'member__party', 'member__riding')]
        }
        
    def get_wordoftheday(self):
        if not self.most_frequent_word:
            self.most_frequent_word = text_utils.most_frequent_word(self.statement_set.filter(procedural=False))
            if self.most_frequent_word:
                self.save()
        return self.most_frequent_word
        
    def generate_wordcloud(self):
        image = text_utils.statements_to_cloud_by_party(self.statement_set.filter(procedural=False))
        self.wordcloud.save("%s-%s.png" % (self.source_id, settings.LANGUAGE_CODE), ContentFile(image), save=True)
        self.save()

    def get_filename(self, language):
        assert self.source_id
        assert language in ('en', 'fr')
        return '%d-%s.xml.gz' % (self.source_id, language)

    def get_filepath(self, language):
        filename = self.get_filename(language)
        if hasattr(settings, 'HANSARD_CACHE_DIR'):
            return os.path.join(settings.HANSARD_CACHE_DIR, filename)
        else:
            return os.path.join(settings.MEDIA_ROOT, 'document_cache', filename)

    def _save_file(self, path, content):
        out = gzip.open(path, 'wb')
        out.write(content)
        out.close()

    def get_cached_xml(self, language):
        if not self.downloaded:
            raise Exception("Not yet downloaded")
        return gzip.open(self.get_filepath(language), 'rb')

    def delete_downloaded(self):
        for lang in ('en', 'fr'):
            path = self.get_filepath(lang)
            if os.path.exists(path):
                os.unlink(path)
        self.downloaded = False
        self.save()

    def _fetch_xml(self, language):
        import urllib2
        return urllib2.urlopen('http://www.parl.gc.ca/HousePublications/Publication.aspx?DocId=%s&Language=%s&Mode=1&xml=true'
        % (self.source_id, language[0].upper())).read()

    def download(self):
        if self.downloaded:
            return True
        if self.date and self.date.year < 2006:
            raise Exception("No XML available before 2006")
        langs = ('en', 'fr')
        paths = [self.get_filepath(l) for l in langs]
        if not all((os.path.exists(p) for p in paths)):
            for path, lang in zip(paths, langs):
                self._save_file(path, self._fetch_xml(lang))
        self.downloaded = True
        self.save()

class Statement(models.Model):
    document = models.ForeignKey(Document)
    time = models.DateTimeField(db_index=True)
    source_id = models.CharField(max_length=15, blank=True)

    slug = models.SlugField(max_length=100, blank=True)
    urlcache = models.CharField(max_length=200, blank=True)

    h1 = models.CharField(max_length=300, blank=True)
    h2 = models.CharField(max_length=300, blank=True)
    h3 = models.CharField(max_length=300, blank=True)

    member = models.ForeignKey(ElectedMember, blank=True, null=True)
    politician = models.ForeignKey(Politician, blank=True, null=True) # a shortcut -- should == member.politician
    who = models.CharField(max_length=300, blank=True)
    who_hocid = models.PositiveIntegerField(blank=True, null=True, db_index=True)
    who_context = models.CharField(max_length=300, blank=True)

    content_en = models.TextField()
    content_fr = models.TextField(blank=True)
    sequence = models.IntegerField(db_index=True)
    wordcount = models.IntegerField()

    procedural = models.BooleanField(default=False, db_index=True)
    written_question = models.CharField(max_length=1, blank=True, choices=(
        ('Q', 'Question'),
        ('R', 'Response')
    ))
    statement_type = models.CharField(max_length=35, blank=True)
    
    bills = models.ManyToManyField(Bill, blank=True)
    mentioned_politicians = models.ManyToManyField(Politician, blank=True, related_name='statements_with_mentions')
        
    class Meta:
        ordering = ('sequence',)
        unique_together = (
            ('document', 'slug')
        )
        
    def save(self, *args, **kwargs):
        if not self.wordcount:
            self.wordcount = parsetools.countWords(self.text_plain())
        self.content_en = self.content_en.replace('\n', '').replace('</p>', '</p>\n').strip()
        self.content_fr = self.content_fr.replace('\n', '').replace('</p>', '</p>\n').strip()
        if ((not self.procedural) and self.wordcount <= 300
            and ( 
                (parsetools.r_notamember.search(self.who) and re.search(r'(Speaker|Chair|président)', self.who))
                or (not self.who)
                or not any(p for p in self.content_en.split('\n') if 'class="procedural"' not in p)
            )):
            # Some form of routine, procedural statement (e.g. somethng short by the speaker)
            self.procedural = True
        if not self.urlcache:
            self.generate_url()
        super(Statement, self).save(*args, **kwargs)
            
    @property
    def date(self):
        return datetime.date(self.time.year, self.time.month, self.time.day)
    
    def generate_url(self):
        self.urlcache = "%s%s/" % (
            self.document.get_absolute_url(),
            (self.slug if self.slug else self.sequence))

    def get_absolute_url(self):
        if not self.urlcache:
            self.generate_url()
        return self.urlcache

    def __unicode__ (self):
        return u"%s speaking about %s around %s" % (self.who, self.topic, self.time)

    @property
    @memoize_property
    def content_floor(self):
        if not self.content_fr:
            return self.content_en
        el, fl = self.content_en.split('\n'), self.content_fr.split('\n')
        if len(el) != len(fl):
            logger.error("Different en/fr paragraphs in %s" % self.get_absolute_url())
            return self.content_en
        r = []
        for e, f in zip(el, fl):
            idx = e.find('data-originallang="')
            if idx and e[idx+19:idx+21] == 'fr':
                r.append(f)
            else:
                r.append(e)
        return u"\n".join(r)

            

    def text_html(self, language=settings.LANGUAGE_CODE):
        return mark_safe(getattr(self, 'content_' + language))

    def text_plain(self, language=settings.LANGUAGE_CODE):
        return (strip_tags(getattr(self, 'content_' + language)
            .replace('\n', '')
            .replace('<br>', '\n')
            .replace('</p>', '\n\n'))
            .strip())

    # temp compatibility
    @property
    def heading(self):
        return self.h1

    @property
    def topic(self):
        return self.h2
        
    def serializable(self):
        v = {
            'url': self.get_absolute_url(),
            'heading': self.heading,
            'topic': self.topic,
            'time': self.time,
            'attribution': self.who,
            'text': self.text_plain()
        }
        if self.member:
            v['politician'] = {
                'id': self.member.politician.id,
                'member_id': self.member.id,
                'name': self.member.politician.name,
                'url': self.member.politician.get_absolute_url(),
                'party': self.member.party.short_name,
                'riding': unicode(self.member.riding),
            }
        return v

    def to_api_dict(self, representation):
        d = dict(
            time=unicode(self.time) if self.time else None,
            attribution={'en': self.who},
            content={'en': self.content_en, 'fr': self.content_fr},
            url=self.get_absolute_url(),
            politician_url=self.politician.get_absolute_url() if self.politician else None,
            politician_role_url=urlresolvers.reverse('politician_role',
                kwargs={'member_id': self.member_id}) if self.member_id else None,
            procedural=self.procedural,
            source_id=self.source_id
        )
        for h in ('h1', 'h2', 'h3'):
            v = getattr(self, h)
            if v:
                d[h] = {'en': v}
        d['document_url'] = d['url'][:d['url'].rstrip('/').rfind('/')+1]
        return d
    
    @property
    @memoize_property    
    def name_info(self):
        info = {
            'post': None,
            'named': True
        }
        if not self.member:
            info['display_name'] = parsetools.r_mister.sub('', self.who)
            if self.who_context:
                if self.who_context in self.who:
                    info['display_name'] = parsetools.r_parens.sub('', info['display_name'])
                    info['post'] = self.who_context
                else:
                    info['post_reminder'] = self.who_context
                if self.who_hocid:
                    info['url'] = '/search/?q=Witness%%3A+%%22%s%%22' % self.who_hocid
        else:
            info['url'] = self.member.politician.get_absolute_url()
            if parsetools.r_notamember.search(self.who):
                info['display_name'] = self.who
                if self.member.politician.name in self.who:
                    info['display_name'] = re.sub(r'\(.+\)', '', self.who)
                info['named'] = False
            elif not '(' in self.who or not parsetools.r_politicalpost.search(self.who):
                info['display_name'] = self.member.politician.name
            else:
                post_match = re.search(r'\((.+)\)', self.who)
                if post_match:
                    info['post'] = post_match.group(1).split(',')[0]
                info['display_name'] = self.member.politician.name
        return info

    @staticmethod
    def set_slugs(statements):
        counter = defaultdict(int)
        for statement in statements:
            slug = slugify(statement.name_info['display_name'])[:50]
            if not slug:
                slug = 'procedural'
            counter[slug] += 1
            statement.slug = slug + '-%s' % counter[slug]

    @property
    def committee_name(self):
        if self.document.document_type != Document.EVIDENCE:
            return ''
        return self.document.committeemeeting.committee.short_name

    @property
    def committee_slug(self):
        if self.document.document_type != Document.EVIDENCE:
            return ''
        return self.document.committeemeeting.committee.slug

class OldSequenceMapping(models.Model):
    document = models.ForeignKey(Document)
    sequence = models.PositiveIntegerField()
    slug = models.SlugField(max_length=100)

    class Meta:
        unique_together = (
            ('document', 'sequence')
        )

    def __unicode__(self):
        return u"%s -> %s" % (self.sequence, self.slug)
            
