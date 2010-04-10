from haystack import site
from haystack import indexes

from parliament.hansards.models import Statement

class StatementIndex(indexes.RealTimeSearchIndex):
    text = indexes.CharField(document=True, model_attr='text_plain')
    sc = indexes.CharField(stored=False, use_template=True)
    date = indexes.DateTimeField(model_attr='time')
    politician = indexes.CharField(use_template=True)
    politician_id = indexes.IntegerField(model_attr='member__politician_id', null=True)
    party = indexes.CharField(model_attr='member__party__short_name', null=True)
    province = indexes.CharField(model_attr='member__riding__province', null=True)
    topic = indexes.CharField(model_attr='topic')
    url = indexes.CharField(model_attr='get_absolute_url', indexed=False)
    
    def get_queryset(self):
        return Statement.objects.all().select_related('member__politician', 'member__party', 'member__riding')

site.register(Statement, StatementIndex)