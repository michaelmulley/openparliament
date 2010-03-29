import urllib
import feedparser

from django.template import Context, loader, RequestContext
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.contrib.syndication.views import Feed
from django.shortcuts import get_object_or_404
from django.contrib.markup.templatetags.markup import markdown
from BeautifulSoup import BeautifulSoup

from parliament.core.models import Politician
from parliament.hansards.models import Statement

GOOGLE_NEWS_URL = 'http://news.google.ca/news?pz=1&cf=all&ned=ca&hl=en&as_maxm=3&q=MP+%%22%s%%22+location%%3Acanada&as_qdr=a&as_drrb=q&as_mind=25&as_minm=2&cf=all&as_maxd=27&scoring=n&output=rss'
def news_items_for_pol(pol):
    feed = feedparser.parse(GOOGLE_NEWS_URL % urllib.quote(pol.name))
    items = []
    for i in feed['entries'][:6]:
        item = {'link': i.link,
                'title': i.title}
        soup = BeautifulSoup(i.summary)
        try:
            item['summary'] = str(soup.findAll('font', size='-1')[1])
        except:
            continue
        items.append(item)
    return items

def politician(request, pol_id):
    try:
        pol = Politician.objects.get(pk=pol_id)
    except Politician.DoesNotExist:
        raise Http404
    
    c = RequestContext(request, {
        'pol': pol,
        'candidacies': pol.candidacy_set.all().order_by('-election__date'),
        'statements': Statement.objects.filter(member__politician=pol).order_by('-time')[:10],
        'newsitems': news_items_for_pol(pol),
    })
    t = loader.get_template("parliament/politician.html")
    return HttpResponse(t.render(c))
    
class PoliticianFeed(Feed):
    
    def get_object(self, request, pol_id):
        return get_object_or_404(Politician, pk=pol_id)
    
    def title(self, pol):
        return pol.name
        
    def link(self, pol):
        return "http://openparliament.ca" + pol.get_absolute_url()
        
    def description(self, pol):
        return "Statements by %s in the House of Commons, from openparliament.ca." % pol.name
        
    def items(self, pol):
        return Statement.objects.filter(member__politician=pol).order_by('-time')[:12]
        
    def item_title(self, statement):
        return statement.topic
        
    def item_link(self, statement):
        return statement.get_absolute_url()
        
    def item_description(self, statement):
        return markdown(statement.text)
        
    def item_pubdate(self, statement):
        return statement.time