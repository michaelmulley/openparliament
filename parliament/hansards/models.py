#coding: utf-8

from collections import defaultdict, OrderedDict
import datetime
import os
from pathlib import Path
import re
from typing import Literal

from django.db import models
from django.conf import settings
from django.urls import reverse
from django.template.defaultfilters import slugify
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

from parliament.core.models import Session, ElectedMember, Politician
from parliament.core import parsetools
from parliament.core.utils import memoize_property, language_property
from parliament.activity import utils as activity
from parliament.search.index import register_search_model

import logging
logger = logging.getLogger(__name__)

class DebateManager(models.Manager):

    def get_queryset(self):
        return super(DebateManager, self).get_queryset().filter(document_type=Document.DEBATE)

class EvidenceManager(models.Manager):

    def get_queryset(self):
        return super(EvidenceManager, self).get_queryset().filter(document_type=Document.EVIDENCE)

class NoStatementManager(models.Manager):
    """Manager restricts to Documents that haven't had statements parsed."""

    def get_queryset(self):
        return super(NoStatementManager, self).get_queryset()\
            .annotate(scount=models.Count('statement'))\
            .exclude(scount__gt=0)

class Document(models.Model):
    
    DEBATE = 'D'
    EVIDENCE = 'E'
    
    document_type = models.CharField(max_length=1, db_index=True, choices=(
        ('D', 'Debate'),
        ('E', 'Committee Evidence'),
    ))
    date = models.DateField(blank=True, null=True)
    number = models.CharField(max_length=6, blank=True) # there exist 'numbers' with letters
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    
    source_id = models.IntegerField(unique=True, db_index=True)
    xml_source_url = models.URLField(blank=True) # for English XML
    
    most_frequent_word = models.CharField(max_length=20, blank=True)
    wordcloud = models.ImageField(upload_to='autoimg/wordcloud', blank=True, null=True)

    downloaded = models.BooleanField(default=False,
        help_text="Has the source data been downloaded?")
    skip_parsing = models.BooleanField(default=False,
        help_text="Don't try to parse this, presumably because of errors in the source.")
    skip_redownload = models.BooleanField(default=False,
        help_text="Don't try to redownload the source.")
    
    first_imported = models.DateTimeField(blank=True, null=True,
        help_text="The first time this document was imported from XML.")
    last_imported = models.DateTimeField(blank=True, null=True,
        help_text="The most recent time this document was imported from XML.")

    public = models.BooleanField("Display on site?", default=False)
    multilingual = models.BooleanField("Content parsed in both languages?", default=False)

    objects = models.Manager()
    debates = DebateManager()
    evidence = EvidenceManager()
    without_statements = NoStatementManager()
    
    class Meta:
        ordering = ('-date',)
    
    def __str__ (self):
        if self.document_type == self.DEBATE:
            return "Hansard #%s for %s (#%s/#%s)" % (self.number, self.date, self.id, self.source_id)
        else:
            return "%s evidence for %s (#%s/#%s)" % (
                self.committeemeeting.committee.short_name, self.date, self.id, self.source_id)
        
    @memoize_property
    def get_absolute_url(self):
        if self.document_type == self.DEBATE:
            return reverse('debate', kwargs={
                'year': self.date.year, 'month': self.date.month, 'day': self.date.day
            })
        elif self.document_type == self.EVIDENCE:
            return self.committeemeeting.get_absolute_url()

    def get_text_analysis_url(self):
        # Let's violate DRY!
        return self.get_absolute_url() + 'text-analysis/'

    def to_api_dict(self, representation):
        d = dict(
            date=str(self.date) if self.date else None,
            number=self.number,
            most_frequent_word={'en': self.most_frequent_word},
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
    @memoize_property
    def source_url(self):
        if self.document_type == self.DEBATE:
            return "https://www.ourcommons.ca/DocumentViewer/%(lang)s/%(sessid)s/house/sitting-%(sitting)s/hansard" % {
                'lang': 'en',
                'sessid': self.session_id,
                'sitting': self.number
            }
        elif self.document_type == self.EVIDENCE:
            return self.committeemeeting.evidence_url
        
    def get_xml_url(self, lang: Literal['en', 'fr']):
        """Returns the URL of the source XML for this document on Parliament's site."""
        if self.xml_source_url:
            if lang == 'fr':
                assert '-E.' in self.xml_source_url
                return self.xml_source_url.replace('-E.', '-F.')
            return self.xml_source_url
        
        if self.document_type == self.DEBATE:
            if self.session.parliamentnum < 39:
                return None
            HANSARD_URL = 'https://www.ourcommons.ca/Content/House/{parliamentnum}{sessnum}/Debates/{sitting:03d}/HAN{sitting:03d}-{lang}.XML'
            return HANSARD_URL.format(parliamentnum=self.session.parliamentnum,
                sessnum=self.session.sessnum, sitting=int(self.number), lang=lang[0].upper())
        
        if self.document_type == self.EVIDENCE:
            from parliament.imports.parl_cmte import get_xml_url_from_documentviewer_url
            evidence_page_url = self.committeemeeting.get_ourcommons_doc_url('evidence', lang='en')
            xml_url_en = get_xml_url_from_documentviewer_url(evidence_page_url)
            if lang == 'fr':
                assert '-E.' in xml_url_en
                return xml_url_en.replace('-E.', '-F.')
            return xml_url_en

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
        return self._topics(self.statement_set.all().values_list('h2_' + settings.LANGUAGE_CODE, 'slug'))
        
    def headings(self):
        """Returns a tuple with (heading, statement slug) for every heading mentioned."""
        return self._topics(self.statement_set.all().values_list('h1_' + settings.LANGUAGE_CODE, 'slug'))
    
    def topics_with_qp(self):
        """Returns the same as topics(), but with a link to Question Period at the start of the list."""
        statements = self.statement_set.all().values_list(
            'h2_' + settings.LANGUAGE_CODE, 'slug', 'h1_' + settings.LANGUAGE_CODE)
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
            minister: Boolean -- is this an elected minister?
            description: Short title or affiliation
        """
        ids_seen = set()
        speakers = dict()
        for st in self.statement_set.filter(who_hocid__isnull=False).values_list(
                'who_' + settings.LANGUAGE_CODE,            # 0
                'who_context_' + settings.LANGUAGE_CODE,    # 1
                'slug',                                     # 2
                'politician__name',                         # 3
                'who_hocid'):                               # 4
            if st[4] in ids_seen:
                continue
            ids_seen.add(st[4])
            if st[3]:
                who = st[3]
            else:
                who = parsetools.r_parens.sub('', st[0])
                who = re.sub(r'^\s*\S+\s+', '', who).strip() # strip honorific
            if who not in speakers:
                info = {
                    'slug': st[2],
                    'politician': bool(st[3]),
                    'minister': bool(st[3] and ('Minister ' in st[1] or 'Ministre ' in st[1])),
                    'source_id': st[4],
                }
                if st[1]:
                    info['description'] = st[1]
                speakers[who] = info
        return speakers

    def outside_speaker_summary(self):
        """Same as speaker_summary, but not the committee members."""
        return {k: v for k, v in self.speaker_summary().items() if v['minister'] or not (v['politician'] or k.startswith('Clerk '))}

    def mp_speaker_summary(self):
        """Same as speaker_summary, but just the committee members."""
        return {k: v for k, v in self.speaker_summary().items() if v['politician'] and not v['minister']}
    
    def save_activity(self):
        statements = self.statement_set.filter(procedural=False).select_related('member', 'politician')
        politicians = set([s.politician for s in statements if s.politician])
        for pol in politicians:
            topics = {}
            wordcount = 0
            for statement in [s for s in statements if s.politician == pol]:
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
                    (seq, text, url) = list(topics.values())[0]
                    activity.save_activity({
                        'meeting': self.committeemeeting,
                        'committee': self.committeemeeting.committee,
                        'text': text,
                        'url': url,
                        'wordcount': wordcount,
                    }, politician=pol, date=self.date, guid='cmte_%s' % url, variety='committee')
        
    def get_xml_path(self, language: Literal['en', 'fr']) -> Path:
        assert language in ('en', 'fr')
        if hasattr(settings, 'HANSARD_CACHE_DIR'):
            basepath = Path(settings.HANSARD_CACHE_DIR)
        else:
            basepath = Path(settings.MEDIA_ROOT) / 'document_cache'
        
        if self.document_type == self.DEBATE:
            assert self.number
            return (basepath / 'debates' / self.session.id /
                                f"{self.session.id}-{self.number}-{language}.xml")
        elif self.document_type == self.EVIDENCE:
            assert self.date
            return (basepath / 'evidence' / str(self.date.year) / str(self.date.month) /
                                f"{self.source_id}-{language}.xml")

    def get_cached_xml(self, language: Literal['en', 'fr']) -> bytes:
        if not self.downloaded:
            raise Exception("Not yet downloaded")
        return self.get_xml_path(language).read_bytes()
   
    def save_xml(self, source_url, xml_en: bytes, xml_fr: bytes, overwrite=False):
        path_en = self.get_xml_path('en')
        path_fr = self.get_xml_path('fr')
        if not overwrite and (path_en.exists() or path_fr.exists()):
            raise Exception("XML files already exist")
        path_en.parent.mkdir(parents=True, exist_ok=True)
        path_en.write_bytes(xml_en)
        path_fr.write_bytes(xml_fr)
        self.xml_source_url = source_url
        self.downloaded = True
        self.save()

@register_search_model
class Statement(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    time = models.DateTimeField(db_index=True)
    source_id = models.CharField(max_length=15, blank=True)

    slug = models.SlugField(max_length=100, blank=True)
    urlcache = models.CharField(max_length=200, blank=True)

    h1_en = models.CharField(max_length=300, blank=True)
    h2_en = models.CharField(max_length=300, blank=True)
    h3_en = models.CharField(max_length=300, blank=True)
    h1_fr = models.CharField(max_length=400, blank=True)
    h2_fr = models.CharField(max_length=400, blank=True)
    h3_fr = models.CharField(max_length=400, blank=True)

    member = models.ForeignKey(ElectedMember, blank=True, null=True, on_delete=models.CASCADE)
    politician = models.ForeignKey(Politician, blank=True, null=True, on_delete=models.CASCADE) # a shortcut -- should == member.politician
    who_en = models.CharField(max_length=300, blank=True)
    who_fr = models.CharField(max_length=500, blank=True)
    who_hocid = models.PositiveIntegerField(blank=True, null=True, db_index=True)
    who_context_en = models.CharField(max_length=300, blank=True)
    who_context_fr = models.CharField(max_length=500, blank=True)

    content_en = models.TextField()
    content_fr = models.TextField(blank=True)
    sequence = models.IntegerField(db_index=True)
    wordcount = models.IntegerField()
    wordcount_en = models.PositiveSmallIntegerField(null=True,
        help_text="# words originally spoken in English")

    procedural = models.BooleanField(default=False, db_index=True)
    written_question = models.CharField(max_length=1, blank=True, choices=(
        ('Q', 'Question'),
        ('R', 'Response')
    ))
    statement_type = models.CharField(max_length=35, blank=True)
    
    mentioned_bills = models.ManyToManyField('bills.Bill', blank=True,
                                             db_table='hansards_statement_bills', related_name='statements_with_mentions')
    bill_debated = models.ForeignKey('bills.Bill', blank=True, null=True, on_delete=models.SET_NULL,
                                     related_name='statements_from_debates')
    bill_debate_stage = models.CharField(max_length=10, blank=True, db_index=True, choices=[
        ('1', 'First reading'),
        ('2', 'Second reading'),
        ('3', 'Third reading'),
        ('report', 'Report stage'),
        ('senate', 'Senate amendments'),
        ('other', 'Other')
    ])
    mentioned_politicians = models.ManyToManyField(Politician, blank=True, related_name='statements_with_mentions')
        
    class Meta:
        ordering = ('sequence',)
        unique_together = (
            ('document', 'slug')
        )

    h1 = language_property('h1')
    h2 = language_property('h2')
    h3 = language_property('h3')
    who = language_property('who')
    who_context = language_property('who_context')

    def save(self, *args, **kwargs):
        self.content_en = self.content_en.replace('\n', '').replace('</p>', '</p>\n').strip()
        self.content_fr = self.content_fr.replace('\n', '').replace('</p>', '</p>\n').strip()
        if self.wordcount_en is None:
            self._generate_wordcounts()
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

    def __str__ (self):
        return "%s speaking about %s around %s" % (self.who, self.topic, self.time)

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
        return "\n".join(r)

    def content_floor_if_necessary(self):
        """Returns text spoken in the original language(s), but only if that would
        be different than the content in the default language."""
        if not (self.content_en and self.content_fr):
            return ''

        lang_matches = re.finditer(r'data-originallang="(\w\w)"',
            getattr(self, 'content_' + settings.LANGUAGE_CODE))
        if any(m.group(1) != settings.LANGUAGE_CODE for m in lang_matches):
            return self.content_floor()

        return ''

    def text_html(self, language=settings.LANGUAGE_CODE):
        html = getattr(self, 'content_' + language)
        html = re.sub(r'data-HoCid="([1-9][0-9]+)"', r'id="\1"', html)
        return mark_safe(html)

    def text_plain(self, language=settings.LANGUAGE_CODE, include_paragraph_urls=False):
        html = getattr(self, 'content_' + language)
        if include_paragraph_urls:
            html = re.sub(r'<p [^>]*id="([1-9][^"]+)"[^>]*>', rf'<p>[{self.urlcache}#\1] ', html)
        return self.html_to_text(html)

    @staticmethod
    def html_to_text(html):
        return strip_tags(
            html
            .replace('\n', '')
            .replace('<br>', '\n')
            .replace('</p>', '\n\n')
            .replace('&amp;', '&')
        ).strip()

    def search_dict(self):      
        name = self.name_info
        d = {
            "text": self.text_plain(),
            # the date is local Ottawa time, not UTC, but we'll pretend for search
            "date": self.time.isoformat() + 'Z',
            "who_hocid": self.who_hocid,
            "topic": self.h2,
            "url": self.get_absolute_url(),
            "doc_url": self.document.get_absolute_url(),
            "committee": self.committee_name,
            "committee_slug": self.committee_slug
        }
        if self.member:
            d['party'] = self.member.party.short_name
            d['province'] = self.member.riding.province
            d['politician_id'] = self.member.politician.identifier

        d['doctype'] = 'committee' if d['committee'] else 'debate'
        d['politician'] = name['display_name']
        d['searchtext'] = f"{name['display_name']} {name['post'] if name['post'] else ''} {d.get('party', '')} {d['topic']} {d['text']}"
        return d
    
    def search_should_index(self):
        return True
    
    @classmethod
    def search_get_qs(cls):
        qs = cls.objects.all().prefetch_related(
            'member__politician', 'member__party', 'member__riding', 'document',
            'document__committeemeeting__committee'
        ).order_by()
        if settings.LANGUAGE_CODE.startswith('fr'):
            qs = qs.exclude(content_fr='')
        return qs

    def _generate_wordcounts(self):
        paragraphs = [
            [], # english
            [], # french
            [] # procedural
        ]

        for para in self.content_en.split('\n'):
            idx = para.find('data-originallang="')
            if idx == -1:
                paragraphs[2].append(para)
            else:
                lang = para[idx+19:idx+21]
                if lang == 'en':
                    paragraphs[0].append(para)
                elif lang == 'fr':
                    paragraphs[1].append(para)
                else:
                    paragraphs[0].append(para)
                    logger.warning("Unrecognized language %s", lang)

        counts = [
            len(self.html_to_text(' '.join(p)).split())
            for p in paragraphs
        ]

        self.wordcount = counts[0] + counts[1]
        self.wordcount_en = counts[0]
        #self.wordcount_procedural = counts[2]

    # temp compatibility
    @property
    def heading(self):
        return self.h1

    @property
    def topic(self):
        return self.h2
        
    def to_api_dict(self, representation):
        d = dict(
            time=str(self.time) if self.time else None,
            attribution={'en': self.who_en, 'fr': self.who_fr},
            content={'en': self.content_en, 'fr': self.content_fr},
            url=self.get_absolute_url(),
            politician_url=self.politician.get_absolute_url() if self.politician else None,
            politician_membership_url=reverse('politician_membership',
                kwargs={'member_id': self.member_id}) if self.member_id else None,
            procedural=self.procedural,
            source_id=self.source_id
        )
        for h in ('h1', 'h2', 'h3'):
            if getattr(self, h):
                d[h] = {'en': getattr(self, h + '_en'), 'fr': getattr(self, h + '_fr')}
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
                if 'Speaker' in info['display_name']:
                    info['speaker'] = True
            elif not '(' in self.who or not parsetools.r_politicalpost.search(self.who):
                info['display_name'] = self.member.politician.name
            else:
                post_match = re.search(r'\((.+)\)', self.who)
                if post_match:
                    info['post'] = post_match.group(1).split(',')[0]
                info['display_name'] = self.member.politician.name
        return info

    @staticmethod
    def set_slugs(statements, with_timestamp=False, substitute_names=dict()):
        counter = defaultdict(int)
        for statement in statements:
            slug = slugify(statement.name_info['display_name'])[:50]
            if not slug:
                slug = 'procedural'            
            if slug in substitute_names:
                slug = substitute_names[slug]
            if with_timestamp:
                slug += f"-{statement.time.strftime('%H%M')}"
                counter[slug] += 1                
                if counter[slug] > 1:
                    slug += f"-{counter[slug]}"
                statement.slug = slug
            else:
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
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    sequence = models.PositiveIntegerField()
    slug = models.SlugField(max_length=100)

    class Meta:
        unique_together = (
            ('document', 'sequence')
        )

    def __str__(self):
        return "%s -> %s" % (self.sequence, self.slug)
            
class OldSlugMapping(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    old_slug = models.SlugField(max_length=100)
    new_slug = models.SlugField(max_length=100)

    class Meta:
        unique_together = (
            ('document', 'old_slug')
        )

    def __str__(self):
        return f"{self.old_slug} -> {self.new_slug}"
