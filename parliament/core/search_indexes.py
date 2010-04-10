from haystack import site
from haystack import indexes

from parliament.core.models import Politician

class PolIndex(indexes.RealTimeSearchIndex):
    text = indexes.CharField(document=True, use_template=True)
    sci = indexes.CharField(use_template=True, stored=False)
    pol_name = indexes.CharField(model_attr='name', indexed=False)
    url = indexes.CharField(model_attr='get_absolute_url', indexed=False)
    #dob = indexes.DateTimeField(model_attr='dob')
    
    def get_queryset(self):
        return Politician.objects.elected()

site.register(Politician, PolIndex)
