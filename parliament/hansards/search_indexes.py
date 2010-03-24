from haystack import site
from haystack import indexes

from parliament.hansards.models import Statement

class StatementIndex(indexes.SearchIndex):
    text = indexes.CharField(document=True, use_template=True)
    date = indexes.DateTimeField(model_attr='time')
    politician = indexes.CharField(model_attr='member__politician', null=True)
    party = indexes.CharField(model_attr='member__party', null=True)
    province = indexes.CharField(model_attr='member__riding__province', null=True)
    
    def get_queryset(self):
        return Statement.objects.all().select_related('member__politician', 'member__party', 'member__riding')

site.register(Statement, StatementIndex)