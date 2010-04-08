from haystack import site
from haystack import indexes

from parliament.bills.models import Bill

class BillIndex(indexes.SearchIndex):
    text = indexes.CharField(document=True, use_template=True, stored=False)
    descr = indexes.CharField(model_attr='name', indexed=False)
    number = indexes.CharField(model_attr='number', indexed=False)
    
site.register(Bill, BillIndex)