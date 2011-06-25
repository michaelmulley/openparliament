from haystack import site
from haystack import indexes

from parliament.search.utils import SearchIndex
from parliament.bills.models import Bill
from parliament.core.models import Session

class BillIndex(SearchIndex):
    text = indexes.CharField(document=True, model_attr='name')
    sci = indexes.CharField(stored=False, use_template=True)
    number = indexes.CharField(model_attr='number', indexed=False)
    url = indexes.CharField(model_attr='get_absolute_url', indexed=False)
    date = indexes.DateField(model_attr='introduced')
    session = indexes.CharField(model_attr='session', indexed=False)

    def prepare_date(self, obj):
        if self.prepared_data.get('date'):
            return self.prepared_data['date']

        return obj.added

    def prepare_session(self, obj):
        if self.prepared_data.get('session'):
            return self.prepared_data['session']

        if obj.introduced:
            return Session.objects.get_by_date(obj.introduced)

        return Session.objects.current()


    
site.register(Bill, BillIndex)