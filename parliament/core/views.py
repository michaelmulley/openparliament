from django.contrib.markup.templatetags.markup import markdown
from django.contrib.syndication.views import Feed
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.template import Context, loader, RequestContext
from django.utils.html import conditional_escape
from django.views.decorators.cache import never_cache

from parliament.core.models import Session, SiteNews
from parliament.bills.models import VoteQuestion
from parliament.hansards.models import Hansard

def home(request):
    
    t = loader.get_template("home.html")
    c = RequestContext(request, {
        'latest_hansard': Hansard.objects.all()[0],
        'sitenews': SiteNews.objects.filter(active=True)[:6],
        'votes': VoteQuestion.objects.filter(session=Session.objects.current())\
            .select_related('bill')[:6],
    })
    return HttpResponse(t.render(c))
    
@never_cache
def closed(request, message=None):
    if not message:
        message = "We're currently down for planned maintenance. We'll be back soon."
    resp = flatpage_response(request, 'closedparliament.ca', message)
    resp.status_code = 503
    return resp
    
def flatpage_response(request, title, message):
    t = loader.get_template("flatpages/default.html")
    c = RequestContext(request, {
        'flatpage': {
            'title': title,
            'content': """<div class="focus"><p>%s</p></div>""" % conditional_escape(message)},
    })
    return HttpResponse(t.render(c))
    
class SiteNewsFeed(Feed):
    
    title = "openparliament.ca: Site news"
    link = "http://openparliament.ca/"
    description = "Announcements about the openparliament.ca site"
    
    def items(self):
        return SiteNews.public.all()[:6]
        
    def item_title(self, item):
        return item.title
        
    def item_description(self, item):
        return markdown(item.text)
        
    def item_link(self):
        return 'http://openparliament.ca/'
        
    def item_guid(self, item):
        return unicode(item.id)
    