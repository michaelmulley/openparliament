from django.conf import settings

from haystack import indexes

from parliament.hansards.models import Statement

class StatementIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, model_attr='text_plain')
    searchtext = indexes.CharField(stored=False, use_template=True)
    date = indexes.DateTimeField(model_attr='time')
    politician = indexes.CharField(use_template=True)
    politician_id = indexes.CharField(model_attr='member__politician__identifier', null=True)
    who_hocid = indexes.IntegerField(model_attr='who_hocid', null=True)
    party = indexes.CharField(model_attr='member__party__short_name', null=True)
    province = indexes.CharField(model_attr='member__riding__province', null=True)
    topic = indexes.CharField(model_attr='h2', null=True)
    url = indexes.CharField(model_attr='get_absolute_url', indexed=False)
    doc_url = indexes.CharField(model_attr='document__get_absolute_url')
    committee = indexes.CharField(model_attr='committee_name')
    committee_slug = indexes.CharField(model_attr='committee_slug')
    doctype = indexes.CharField(null=True)

    def get_model(self):
        return Statement
    
    def index_queryset(self, using=None):
        qs = Statement.objects.all().prefetch_related(
            'member__politician', 'member__party', 'member__riding', 'document',
            'document__committeemeeting__committee'
        ).order_by('-date')
        if settings.LANGUAGE_CODE.startswith('fr'):
            qs = qs.exclude(content_fr='')
        return qs

    def prepare_doctype(self, obj):
        if obj.committee_name:
            return 'committee'
        else:
            return 'debate'
