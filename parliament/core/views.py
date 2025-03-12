import datetime

from django.conf import settings
from django.contrib.syndication.views import Feed
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.template import loader
from django.utils.html import conditional_escape
from django.views.decorators.cache import never_cache

from parliament.core.models import Session, SiteNews
from parliament.bills.models import VoteQuestion, Bill
from parliament.hansards.models import Document
from parliament.hansards.utils import get_hansard_sections_or_summary
from parliament.core.templatetags.markup import markdown
from parliament.text_analysis.models import TextAnalysis

def home(request):
    t = loader.get_template("home.html")
    latest_hansard = Document.debates.filter(date__isnull=False, public=True)[0]
    hansard_topics_data, hansard_topics_summary_obj = get_hansard_sections_or_summary(latest_hansard)
    recently_debated_bills = Bill.objects.filter(
            latest_debate_date__isnull=False).order_by('-latest_debate_date').values(
                'session', 'number', 'name_en', 'short_title_en'
            )[:6]
    c = {
        'latest_hansard': latest_hansard,
        'hansard_topics_data': hansard_topics_data,
        'hansard_topics_ai_summary': hansard_topics_summary_obj,
        'sitenews': SiteNews.objects.filter(active=True,
            date__gte=datetime.datetime.now() - datetime.timedelta(days=90))[:6],
        'votes': VoteQuestion.objects.filter(session=Session.objects.current())
            .select_related('bill')[:6],
        'recently_debated_bills': recently_debated_bills,
        'wordcloud_js': TextAnalysis.objects.get_wordcloud_js(
            key=latest_hansard.get_text_analysis_url())
    }
    return HttpResponse(t.render(c, request))
    
@never_cache
def closed(request, message=None):
    if not message:
        message = "We're currently down for planned maintenance. We'll be back soon."
    resp = flatpage_response(request, 'closedparliament.ca', message)
    resp.status_code = 503
    return resp

@never_cache
def db_readonly(request, *args, **kwargs):
    title = "Temporarily unavailable"
    message = """We're currently running on our backup database, and this particular functionality is down.
        It should be back up soon. Sorry for the inconvenience!"""
    resp = flatpage_response(request, title, message)
    resp.status_code = 503
    return resp

def disable_on_readonly_db(view):
    if settings.PARLIAMENT_DB_READONLY:
        return db_readonly
    return view
    
def flatpage_response(request, title, message):
    t = loader.get_template("flatpages/default.html")
    c = {
        'flatpage': {
            'title': title,
            'content': """<div class="row align-right"><div class="main-col"><p>%s</p></div></div>""" % conditional_escape(message)
        },
    }
    return HttpResponse(t.render(c, request))
    
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
        return str(item.id)
    