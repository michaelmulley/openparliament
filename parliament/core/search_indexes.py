from haystack import site
from haystack import indexes

from parliament.core.models import Politician
from parliament.search.utils import SearchIndex

class PolIndex(SearchIndex):
    text = indexes.CharField(document=True, use_template=True)
    boosted = indexes.CharField(use_template=True, stored=False)
    politician = indexes.CharField(model_attr='name', indexed=False)
    party = indexes.CharField(model_attr='latest_member__party__short_name')
    province = indexes.CharField(model_attr='latest_member__riding__province')
    url = indexes.CharField(model_attr='get_absolute_url', indexed=False)
    #dob = indexes.DateTimeField(model_attr='dob')
    
    def get_queryset(self):
        return Politician.objects.elected()

site.register(Politician, PolIndex)
