from haystack import site
from haystack import indexes

from parliament.search.index import SearchIndex
from parliament.bills.models import Bill
from parliament.core.models import Session


class BillIndex(SearchIndex):
    text = indexes.CharField(document=True, model_attr='name')
    searchtext = indexes.CharField(model_attr='name')
    boosted = indexes.CharField(stored=False, use_template=True)
    number = indexes.CharField(model_attr='number', indexed=False)
    url = indexes.CharField(model_attr='get_absolute_url', indexed=False)
    date = indexes.DateField(model_attr='introduced', null=True)
    session = indexes.CharField(model_attr='session', indexed=False, null=True)

    def prepare_session(self, obj):
        if self.prepared_data.get('session'):
            return self.prepared_data['session']

        if obj.introduced:
            return Session.objects.get_by_date(obj.introduced)

        return Session.objects.current()


site.register(Bill, BillIndex)
