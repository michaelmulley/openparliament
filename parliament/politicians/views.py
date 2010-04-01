import urllib
import feedparser

from django.template import Context, loader, RequestContext
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.contrib.syndication.views import Feed
from django.shortcuts import get_object_or_404
from django.contrib.markup.templatetags.markup import markdown
from django.utils.http import urlquote
from django.views.generic.list_detail import object_list
from BeautifulSoup import BeautifulSoup

from parliament.core.models import Politician, ElectedMember
from parliament.hansards.models import Statement

GOOGLE_NEWS_URL = 'http://news.google.ca/news?pz=1&cf=all&ned=ca&hl=en&as_maxm=3&q=MP+%%22%s%%22+location%%3Acanada&as_qdr=a&as_drrb=q&as_mind=25&as_minm=2&cf=all&as_maxd=27&scoring=n&output=rss'
def news_items_for_pol(pol):
    feed = feedparser.parse(GOOGLE_NEWS_URL % urlquote(pol.name))
    items = []
    for i in feed['entries'][:6]:
        item = {'link': i.link,
                'title': i.title}
        soup = BeautifulSoup(i.summary)
        try:
            item['summary'] = str(soup.findAll('font', size='-1')[1])
        except Exception, e:
            print e
            continue
        items.append(item)
    return items
    
def current_mps(request):
    return object_list(request,
        queryset=ElectedMember.objects.current().order_by('riding__province', 'politician__name_family').select_related('politician', 'riding', 'party'),
        template_name='politicians/electedmember_list.html',
        extra_context={'title': 'Current Members of Parliament'})
        
def former_mps(request):
    former_members = ElectedMember.objects.all()\
        .order_by('riding__province', 'politician__name_family', '-start_date')\
        .select_related('politician', 'riding', 'party')
    seen = set()
    object_list = []
    for member in former_members:
        if member.politician.id not in seen:
            if member.end_date:
                # Not a current MP
                object_list.append(member)
            seen.add(member.politician.id)
    
    c = RequestContext(request, {
        'object_list': object_list,
        'title': 'Former MPs (since 1994)'
    })
    t = loader.get_template("politicians/former_electedmember_list.html")
    return HttpResponse(t.render(c))

def politician(request, pol_id):
    try:
        pol = Politician.objects.get(pk=pol_id)
    except Politician.DoesNotExist:
        raise Http404
    
    c = RequestContext(request, {
        'pol': pol,
        'member': pol.latest_member,
        'candidacies': pol.candidacy_set.all().order_by('-election__date'),
        'electedmembers': pol.electedmember_set.all().order_by('-start_date'),
        'statements': Statement.objects.filter(politician=pol).order_by('-time')[:10],
        #'newsitems': news_items_for_pol(pol),
    })
    t = loader.get_template("politicians/politician.html")
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