from haystack import site
from haystack import indexes

from parliament.search.index import SearchIndex
from parliament.bills.models import Bill
from parliament.core.models import Session


class BillIndex(SearchIndex):
    text = indexes.CharField(document=True, model_attr='get_text')
    searchtext = indexes.CharField(use_template=True)
    boosted = indexes.CharField(stored=False, use_template=True)
    title = indexes.CharField(model_attr='name')
    number = indexes.CharField(model_attr='number', indexed=False)
    url = indexes.CharField(model_attr='get_absolute_url', indexed=False)
    date = indexes.DateField(model_attr='latest_date', null=True)
    session = indexes.CharField(model_attr='session', indexed=False, null=True)
    politician = indexes.CharField(model_attr='sponsor_politician__name', null=True)
    politician_id = indexes.CharField(model_attr='sponsor_politician__identifier', null=True)
    party = indexes.CharField(model_attr='sponsor_member__party__short_name', null=True)
    doctype = indexes.CharField(default='bill')

    def prepare_session(self, obj):
        if self.prepared_data.get('session'):
            return self.prepared_data['session']

        if obj.introduced:
            return Session.objects.get_by_date(obj.introduced)

        return Session.objects.current()

    def get_queryset(self):
        return Bill.objects.all().prefetch_related(
            'sponsor_politician', 'sponsor_member', 'sponsor_member__party'
        )

site.register(Bill, BillIndex)
