from haystack import indexes

from parliament.core.models import Politician

class PolIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    boosted = indexes.CharField(use_template=True, stored=False)
    politician = indexes.CharField(model_attr='name', indexed=False)
    party = indexes.CharField(model_attr='latest_member__party__short_name')
    province = indexes.CharField(model_attr='latest_member__riding__province')
    url = indexes.CharField(model_attr='get_absolute_url', indexed=False)
    doctype = indexes.CharField(default='mp')
    
    def index_queryset(self, using=None):
        return Politician.objects.elected()

    def get_model(self):
        return Politician

    def should_obj_be_indexed(self, obj):
        # Currently used only in live updates, not batch indexing
        return bool(obj.latest_member)
