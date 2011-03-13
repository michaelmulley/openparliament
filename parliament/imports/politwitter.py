import re
import urllib2

from django.conf import settings

from lxml import objectify
import twitter

from parliament.core.models import Politician, PoliticianInfo

import logging
logger = logging.getLogger(__name__)

def import_twitter_ids():
    source = urllib2.urlopen('http://politwitter.ca/api.php?format=xml&call=listmp')
    tree = objectify.parse(source)
    for member in tree.xpath('//member'):
        if not member.website_official:
            logger.info("No website for %s" % member.name)
            continue
        parlid = re.search(r'Key=(\d+)&', str(member.website_official)).group(1)
        pol = Politician.objects.get_by_parl_id(parlid)
        current = pol.info().get('twitter')
        new = str(member.twitter_username)
        if str(current).lower() != new.lower():
            logger.error(u"Twitter username change for %s: %s -> %s"
                % (pol, current, new))
            if not current:
                pol.set_info('twitter', new)
                
def update_twitter_list():
    from twitter import twitter_globals
    twitter_globals.POST_ACTIONS.append('create_all')
    t = twitter.Twitter(auth=twitter.OAuth(**settings.TWITTER_OAUTH), domain='api.twitter.com/1')
    current_names = set(PoliticianInfo.objects.exclude(value='').filter(schema='twitter').values_list('value', flat=True))
    list_names= set()
    cursor = -1
    while cursor:
        result = t.user.listname.members(
          user=settings.TWITTER_USERNAME, listname=settings.TWITTER_LIST_NAME,
          cursor=cursor)
        for u in result['users']:
            list_names.add(u['screen_name'])
        cursor = result['next_cursor']
    not_in_db = (list_names - current_names)
    if not_in_db:
        logger.error("Users on list, not in DB: %r" % not_in_db)
    
    not_on_list = (current_names - list_names)
    t.user.listname.members.create_all(user=settings.TWITTER_USERNAME, listname=settings.TWITTER_LIST_NAME,
        screen_name=','.join(not_on_list))
    logger.warning("Users added to Twitter list: %r" % not_on_list)
        
