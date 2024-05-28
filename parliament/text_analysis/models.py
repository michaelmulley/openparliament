import datetime
import json
from operator import itemgetter

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.template.defaultfilters import escapejs
from django.utils.safestring import mark_safe

from parliament.text_analysis.analyze import analyze_statements

class TextAnalysisManager(models.Manager):

    def get_or_create_from_statements(self, key, qs, corpus_name,
            lang=settings.LANGUAGE_CODE, always_update=False, expiry_days=None):
        try:
            analysis = self.get(key=key, lang=lang)
            if analysis.expired:
                analysis.delete()
                analysis = TextAnalysis(key=key, lang=lang)
        except ObjectDoesNotExist:
            analysis = TextAnalysis(key=key, lang=lang)
        if always_update or not analysis.probability_data_json:
            # Set a cache value so we don't have multiple server process trying
            # to do the same calculations at the same time
            cache_key = 'text_analysis:' + key
            if (not cache.get(cache_key)) and qs.exists():
                cache.set(cache_key, True, 60)
                analysis.probability_data_json = json.dumps(analyze_statements(qs, corpus_name))
                if expiry_days:
                    analysis.expires = datetime.datetime.now() + datetime.timedelta(days=expiry_days)
                analysis.save()
        return analysis

    def create_from_statements(self, key, qs, corpus_name, lang=settings.LANGUAGE_CODE):
        return self.get_or_create_from_statements(key, qs, corpus_name, lang, always_update=True)

    def get_wordcloud_js(self, key, lang=settings.LANGUAGE_CODE):
        data = self.filter(key=key, lang=lang).values_list('probability_data_json', 'expires')
        if data and (data[0][1] is None or data[0][1] > datetime.datetime.now()):
            js = 'OP.wordcloud.drawSVG(%s, wordcloud_opts);' % data[0][0]
        elif settings.PARLIAMENT_GENERATE_TEXT_ANALYSIS:
            js = '$.getJSON("%s", function(data) { if (data) OP.wordcloud.drawSVG(data, wordcloud_opts); });' % escapejs(key)
        else:
            js = ''
        return mark_safe(js)

class TextAnalysis(models.Model):

    key = models.CharField(max_length=150, db_index=True, help_text="A URL to a view that calculates this object")
    lang = models.CharField(max_length=2)

    updated = models.DateTimeField(default=datetime.datetime.now)
    expires = models.DateTimeField(blank=True, null=True)

    probability_data_json = models.TextField()

    objects = TextAnalysisManager()

    class Meta:
        unique_together = [('key', 'lang')]
        verbose_name_plural = 'Text analyses'

    def __str__(self):
        return "%s (%s)" % (self.key, self.lang)

    @property
    def expired(self):
        return self.expires and self.expires < datetime.datetime.now()

    @property
    def probability_data(self):
        return json.loads(self.probability_data_json) if self.probability_data_json else None

    @property
    def top_word(self):
        d = self.probability_data
        if d is None:
            return
        onegrams = (w for w in d if w['text'].count(' ') == 0)
        return max(onegrams, key=itemgetter('score'))['text']
