from haystack import site
from haystack import indexes

from parliament.core.models import Politician

class PolIndex(indexes.SearchIndex):
    text = indexes.CharField(document=True, use_template=True)
    #dob = indexes.DateTimeField(model_attr='dob')
    
    def get_queryset(self):
        return Politician.objects.elected()

site.register(Politician, PolIndex)
