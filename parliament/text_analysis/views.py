from django.conf import settings
from django.http import HttpResponse, Http404
from django.views.generic import View

from parliament.text_analysis.models import TextAnalysis

class TextAnalysisView(View):
    """Returns JSON text analysis data. Subclasses must define get_qs."""

    corpus_name = 'default'
    expiry_days = None

    def get(self, request, **kwargs):
        if not settings.PARLIAMENT_GENERATE_TEXT_ANALYSIS:
            raise Http404
        try:
            analysis = self.get_analysis(request, **kwargs)
        except IOError:
            raise Http404
        return HttpResponse(analysis.probability_data_json, content_type='application/json')

    def get_key(self, request, **kwargs):
        return request.path

    def get_qs(self, request, **kwargs):
        raise NotImplementedError

    def get_corpus_name(self, request, **kwargs):
        return self.corpus_name

    def get_analysis(self, request, **kwargs):
        return TextAnalysis.objects.get_or_create_from_statements(
            key=self.get_key(request, **kwargs),
            qs=self.get_qs(request, **kwargs),
            corpus_name=self.get_corpus_name(request, **kwargs),
            expiry_days=self.expiry_days
        )
