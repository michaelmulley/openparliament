"""
Update MP biographical data from the lovely Represent API
"""

import json
import urllib2
from urlparse import urljoin
from time import sleep

from django.conf import settings
from django.db import transaction

import twitter

from parliament.core.models import Politician, Session, PoliticianInfo, Riding

import logging
logger = logging.getLogger(__name__)

def update_mps_from_represent(change_twitter=False, download_headshots=False):

    req = urllib2.urlopen('https://represent.opennorth.ca/representatives/house-of-commons/?limit=500')
    data = json.load(req)

    session = Session.objects.current()

    twitter_updated = False

    for mp_info in data['objects']:
        try:
            pol = Politician.objects.get_by_name(mp_info['name'], session=session)
        except Politician.DoesNotExist:
            logger.error("Could not find politician %s from Represent" % mp_info['name'])
            continue

        def _update(fieldname, value):
            if value == '':
                value = None
            if value == pol.info().get(fieldname):
                return
            if value is None:
                pol.del_info(fieldname)
            pol.set_info(fieldname, value)

        _update('email', mp_info.get('email'))
        _update('web_site', mp_info.get('personal_url'))

        constituency_offices = []
        for office in mp_info['offices']:
            if office['type'] == 'legislature':
                _update('phone', office.get('tel'))
                _update('fax', office.get('fax'))
            elif office.get('postal'):
                formatted = office['postal']
                if office.get('tel'):
                    formatted += '\nPhone: %s' % office['tel']
                constituency_offices.append(formatted.replace('\n\n', '\n'))
        if constituency_offices:
            _update('constituency_offices', '\n\n'.join(constituency_offices))

        if (not pol.headshot) and mp_info.get('photo_url'):
            if download_headshots:
                pol.download_headshot(mp_info['photo_url'])
            else:
                logger.warning("Photo available: %s for %s" % (mp_info.get('photo_url'), pol))

        if mp_info.get('extra') and mp_info['extra'].get('twitter'):
            screen_name = mp_info['extra']['twitter'].split('/')[-1]
            if not pol.info().get('twitter'):
                pol.set_info('twitter', screen_name)
                pol.set_info('twitter_id', get_id_from_screen_name(screen_name))
                twitter_updated = True
            elif pol.info().get('twitter') != screen_name:
                if change_twitter:
                    pol.set_info('twitter', screen_name)
                    pol.set_info('twitter_id', get_id_from_screen_name(screen_name))
                    twitter_updated = True
                else:
                    logger.warning("Potential twitter change for %s: existing %s new %s" % (
                        pol, pol.info()['twitter'], screen_name))
    
    if twitter_updated:
        update_twitter_list()
            

def update_twitter_list():
    from twitter import twitter_globals
    twitter_globals.POST_ACTIONS.append('create_all')
    t = twitter.Twitter(auth=twitter.OAuth(**settings.TWITTER_OAUTH), domain='api.twitter.com/1.1')
    current_names = set(PoliticianInfo.objects.exclude(value='').filter(schema='twitter').values_list('value', flat=True))
    list_names = set()
    cursor = -1
    while cursor:
        result = t.lists.members(
          owner_screen_name=settings.TWITTER_USERNAME, slug=settings.TWITTER_LIST_NAME,
          cursor=cursor)
        for u in result['users']:
            list_names.add(u['screen_name'])
        cursor = result['next_cursor']
    not_in_db = (list_names - current_names)
    if not_in_db:
        logger.error("Users on list, not in DB: %r" % not_in_db)
    
    not_on_list = (current_names - list_names)
    t.lists.members.create_all(owner_screen_name=settings.TWITTER_USERNAME, slug=settings.TWITTER_LIST_NAME,
        screen_name=','.join(not_on_list))
    logger.warning("Users added to Twitter list: %r" % not_on_list)
    
def get_id_from_screen_name(screen_name):
    t = twitter.Twitter(auth=twitter.OAuth(**settings.TWITTER_OAUTH), domain='api.twitter.com/1.1')
    return t.users.show(screen_name=screen_name)['id']

@transaction.atomic
def update_ridings_from_represent(boundary_set='federal-electoral-districts'):

    Riding.objects.filter(current=True).update(current=False)

    base_url = 'http://represent.opennorth.ca/'
    req = urllib2.urlopen(urljoin(base_url, '/boundaries/federal-electoral-districts/?limit=500'))
    riding_list = json.load(req)
    riding_urls = [r['url'] for r in riding_list['objects']]
    for riding_url in riding_urls:
        req = urllib2.urlopen(urljoin(base_url, riding_url))
        riding_data = json.load(req)
        edid = int(riding_data['external_id'])
        name = riding_data['metadata']['ENNAME']
        name_fr = riding_data['metadata']['FRNAME']
        prov = riding_data['metadata']['PROVCODE']
        try:
            riding = Riding.objects.get_by_name(name)
            riding.name = name # just in case of slight punctuation differences
        except Riding.DoesNotExist:
            riding = Riding(name=name)
        riding.edid = edid
        riding.name_fr = name_fr
        riding.province = prov
        riding.current = True
        riding.save()
        sleep(.1)






