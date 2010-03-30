from haystack import site
from haystack import indexes

from parliament.bills.models import Bill

class BillIndex(indexes.SearchIndex):
    text = indexes.CharField(document=True, use_template=True)
    
site.register(Bill, BillIndex)