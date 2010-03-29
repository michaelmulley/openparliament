from django.template import Context, loader, RequestContext
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.contrib.syndication.views import Feed
from django.shortcuts import get_object_or_404
from django.views.generic.list_detail import object_list

from parliament.bills.models import Bill

def bill(request, bill_id):
    
    bill = get_object_or_404(Bill, pk=bill_id)
    
    statements = bill.statement_set.all().order_by('-time')[:10]
    
    c = RequestContext(request, {
        'bill': bill,
        'statements': statements,
    })
    t = loader.get_template("bills/bill.html")
    return HttpResponse(t.render(c))
    
def all_bills(request):
    return object_list(request, queryset=Bill.objects.all())