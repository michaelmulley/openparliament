from haystack import site
from haystack import indexes

from parliament.core.models import Politician
from parliament.hansards.models import Statement

class PolIndex(indexes.SearchIndex):
    text = indexes.CharField(document=True, use_template=True)
    #dob = indexes.DateTimeField(model_attr='dob')
    
class StatementIndex(indexes.SearchIndex):
    text = indexes.CharField(document=True, use_template=True)
    date = indexes.DateTimeField(model_attr='time')

site.register(Politician, PolIndex)
site.register(Statement, StatementIndex)
