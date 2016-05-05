import email
import datetime
import time

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

import requests
from requests_oauthlib import OAuth1

from parliament.core.models import Politician
from parliament.activity import utils as activity

import logging
logger = logging.getLogger(__name__)

def save_tweets():
    OLDEST = datetime.date.today() - datetime.timedelta(days=1)

    pols = Politician.objects.current()
    for pol in pols:
        if 'twitter' not in pol.info():
            continue
        if 'twitter_id' in pol.info():
            twitter_id = pol.info()['twitter_id']
        else:
            try:
                twitter_id = get_id_from_screen_name(pol.info()['twitter'])
                pol.set_info('twitter_id', twitter_id)
            except ObjectDoesNotExist:
                logger.error('Screen name appears to be invalid: %s', pol.info()['twitter'])
                pol.del_info('twitter')
                continue

        try:
            timeline = twitter_api_request('statuses/user_timeline', {'user_id': twitter_id, 'include_rts': False})
        except ObjectDoesNotExist:
            logger.warning("Invalid twitter ID for %s", pol)
            continue
        except requests.HTTPError as e:
            logger.exception("HTTPError for %s %s", pol, e)
            continue
        except requests.ConnectionError:
            continue

        if timeline and timeline[0]['user']['screen_name'] != pol.info()['twitter']:
            # Changed screen name
            new_name = timeline[0]['user']['screen_name']
            logger.warning("Screen name change: new %s old %s", new_name, pol.info()['twitter'])
            pol.set_info('twitter', new_name)

        timeline.reverse()
        for tweet in timeline:
            date = datetime.date.fromtimestamp(
                email.utils.mktime_tz(
                    email.utils.parsedate_tz(tweet['created_at'])
                )
            ) # fuck you, time formats
            if date < OLDEST:
                continue

            guid = 'twit_%s' % tweet['id']
            # Twitter apparently escapes < > but not & "
            # so I'm clunkily unescaping lt and gt then reescaping in the template
            text = tweet['text'].replace('&lt;', '<').replace('&gt;', '>')
            activity.save_activity({'text': text}, politician=pol,
                date=date, guid=guid, variety='twitter')
            
def get_id_from_screen_name(screen_name):
    return twitter_api_request('users/show', params={'screen_name': screen_name})['id']
        
def twitter_api_request(endpoint, params=None):
    url = 'https://api.twitter.com/1.1/' + endpoint + '.json'
    auth = OAuth1(
        settings.TWITTER_OAUTH['consumer_key'],
        settings.TWITTER_OAUTH['consumer_secret'],
        settings.TWITTER_OAUTH['token'],
        settings.TWITTER_OAUTH['token_secret'],
    )
    resp = requests.get(url, auth=auth, params=params)
    if resp.status_code == 200:
        return resp.json()
    elif resp.status_code == 429:
        # We're rate-limited
        limit_expires = int(resp.headers['x-rate-limit-reset'])
        time.sleep(max(limit_expires - time.time(), 10))
        return twitter_api_request(endpoint, params)
    elif resp.status_code == 404:
        raise ObjectDoesNotExist
    elif resp.status_code == 401:
        # Return empty list for protected accounts
        return []

    resp.raise_for_status()
