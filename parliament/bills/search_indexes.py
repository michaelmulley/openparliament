#coding: utf-8

from haystack import indexes

from parliament.bills.models import Bill
from parliament.core.models import Session


class BillIndex(indexes.SearchIndex, indexes.Indexable):
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

    def prepare_title(self, obj):
        if len(obj.name) < 150:
            return obj.name
        elif obj.short_title:
            return obj.short_title
        else:
            return obj.name[:140] + '…'

    def index_queryset(self, using=None):
        return Bill.objects.all().prefetch_related(
            'sponsor_politician', 'sponsor_member', 'sponsor_member__party'
        )

    def get_model(self):
        return Bill
