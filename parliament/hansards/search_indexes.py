from haystack import site
from haystack import indexes

from parliament.search.utils import SearchIndex
from parliament.hansards.models import Statement

class StatementIndex(SearchIndex):
    text = indexes.CharField(document=True, model_attr='text_plain')
    searchtext = indexes.CharField(stored=False, use_template=True)
    date = indexes.DateTimeField(model_attr='time')
    politician = indexes.CharField(use_template=True)
    politician_id = indexes.CharField(model_attr='member__politician__identifier', null=True)
    who_hocid = indexes.IntegerField(model_attr='who_hocid', null=True)
    party = indexes.CharField(model_attr='member__party__short_name', null=True)
    province = indexes.CharField(model_attr='member__riding__province', null=True)
    topic = indexes.CharField(model_attr='topic')
    url = indexes.CharField(model_attr='get_absolute_url', indexed=False)
    committee = indexes.CharField(model_attr='committee_name')
    committee_slug = indexes.CharField(model_attr='committee_slug')
    doctype = indexes.CharField(null=True)
    
    def get_queryset(self):
        return Statement.objects.all().prefetch_related(
            'member__politician', 'member__party', 'member__riding', 'document',
            'document__committeemeeting__committee'
        ).order_by('-date')

    def prepare_doctype(self, obj):
        if obj.committee_name:
            return 'committee'
        else:
            return 'debate'

site.register(Statement, StatementIndex)