from haystack import site
from haystack import indexes

from parliament.search.utils import SearchIndex
from parliament.bills.models import Bill

class BillIndex(SearchIndex):
    text = indexes.CharField(document=True, model_attr='name')
    sci = indexes.CharField(stored=False, use_template=True)
    number = indexes.CharField(model_attr='number', indexed=False)
    url = indexes.CharField(model_attr='get_absolute_url', indexed=False)
    date = indexes.DateField(model_attr='session__start')
    session = indexes.CharField(model_attr='session', indexed=False)
    
site.register(Bill, BillIndex)