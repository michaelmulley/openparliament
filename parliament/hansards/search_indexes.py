from haystack import site
from haystack import indexes

from parliament.hansards.models import Statement

class StatementIndex(indexes.SearchIndex):
    text = indexes.CharField(document=True, use_template=True, stored=False)
    descr = indexes.CharField(model_attr='text_plain', indexed=False)
    hansard_id = indexes.IntegerField(model_attr='hansard_id', indexed=False)
    date = indexes.DateTimeField(model_attr='time')
    politician = indexes.CharField(use_template=True)
    politician_id = indexes.IntegerField(model_attr='member__politician_id', null=True)
    sequence = indexes.IntegerField(model_attr='sequence')
    party = indexes.CharField(model_attr='member__party__short_name', null=True)
    province = indexes.CharField(model_attr='member__riding__province', null=True)
    topic = indexes.CharField(model_attr='topic')
    
    def get_queryset(self):
        return Statement.objects.all().select_related('member__politician', 'member__party', 'member__riding')

site.register(Statement, StatementIndex)