import re
import urllib2

from django.conf import settings

from lxml import etree, objectify
import twitter

from parliament.core.models import Politician, PoliticianInfo, Session

import logging
logger = logging.getLogger(__name__)

def import_twitter_ids():
    source = urllib2.urlopen('http://politwitter.ca/api.php?format=xml&call=listmp')
    # politwitter XML sometimes includes invalid entities
    parser = objectify.makeparser(recover=True)
    tree = objectify.parse(source, parser)
    current_session = Session.objects.current()
    for member in tree.xpath('//member'):
        try:
            pol = Politician.objects.get_by_name(unicode(member.name), session=current_session)
        except Politician.DoesNotExist:
            print "Could not find politician %r" % member.name
        current = pol.info().get('twitter')
        new = str(member.twitter_username)
        if new and str(current).lower() != new.lower():
            logger.error(u"Twitter username change for %s: %s -> %s"
                % (pol, current, new))
            if not current:
                try:
                    pol.set_info('twitter_id', get_id_from_screen_name(new))
                    pol.set_info('twitter', new)
                except Exception as e:
                    print repr(e)
                
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
    
def get_id_from_screen_name(screen_name):
    t = twitter.Twitter(auth=twitter.OAuth(**settings.TWITTER_OAUTH), domain='api.twitter.com/1.1')
    return t.users.show(screen_name=screen_name)['id']
    
def get_ids_from_screen_names():
    for p in Politician.objects.current():
        if 'twitter' in p.info() and 'twitter_id' not in p.info():
            try:
                p.set_info('twitter_id', get_id_from_screen_name(p.info()['twitter']))
            except Exception:
                logger.exception(u"Couldn't get twitter ID for %s" % p.name)
        
