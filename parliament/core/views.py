from django.template import Context, loader, RequestContext
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.contrib.markup.templatetags.markup import markdown
from django.contrib.syndication.views import Feed

from parliament.hansards.models import Hansard
from parliament.core.models import SiteNews

def home(request):
    
    t = loader.get_template("home.html")
    c = RequestContext(request, {
        'latest_hansard': Hansard.objects.all()[0],
        'sitenews': SiteNews.objects.filter(active=True)[:6],
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
    