import feedparser
import datetime
import hashlib

from django.utils.http import urlquote
from BeautifulSoup import BeautifulSoup
from django.utils.html import strip_tags

from parliament.activity import utils as activity

import logging

logger = logging.getLogger(__name__)

GOOGLE_NEWS_URL = 'https://news.google.ca/news?pz=1&cf=all&ned=ca&hl=en&as_maxm=3&q=%s&as_qdr=a&as_drrb=q&as_mind=25&as_minm=2&cf=all&as_maxd=27&scoring=n&output=rss'
def get_feed(pol):
    return feedparser.parse(GOOGLE_NEWS_URL % urlquote(get_query_string(pol)))
    
def get_query_string(pol):
    if 'googlenews_query' in pol.info():
        return pol.info()['googlenews_query']
    names = pol.alternate_names()
    if len(names) > 1:
        q = '( ' + ' OR '.join(['"%s"' % name for name in names]) + ')'
    else:
        q = '"%s"' % pol.name
    q += ' AND ("MP" OR "Member of Parliament") location:canada'
    return q
    
def news_items_for_pol(pol):
    feed = get_feed(pol)
    items = []
    for i in feed['entries'][:10]:
        if 'URL is deprecated' in i.title:
            continue # temp fix
        item = {'url': i.link}
        title_elements = i.title.split('-')
        item['source'] = title_elements.pop().strip()
        item['title'] = '-'.join(title_elements).strip()
        item['date'] = datetime.date(*i.updated_parsed[:3])
        h = hashlib.md5()
        h.update(i.id)
        item['guid'] = 'gnews_%s_%s' % (pol.id, h.hexdigest())
        soup = BeautifulSoup(i.summary)
        try:
            item['summary'] = strip_tags(unicode(soup.findAll('font', size='-1')[1]))
        except Exception as e:
            logger.exception("Error getting news for %s" % pol.slug)
            continue
        if pol.name not in item['summary']:
            continue
        items.append(item)
    return items
    
def save_politician_news(pol):
    items = news_items_for_pol(pol)
    for item in items:
        activity.save_activity(item, politician=pol, date=item['date'], guid=item['guid'], variety='gnews')