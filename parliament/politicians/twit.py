import email
import datetime

from django.conf import settings
import twitter

from parliament.core.models import Politician, PoliticianInfo
from parliament.activity import utils as activity

def save_tweets():
    twitter_to_pol = dict([(i.value.lower(), i.politician) for i in PoliticianInfo.objects.filter(schema='twitter').select_related('politician')])
    
    twit = twitter.Twitter(settings.TWITTER_USERNAME, settings.TWITTER_PASSWORD)
    statuses = twit.openparlca.lists.mps.statuses(per_page=200)
    statuses.reverse()
    for status in statuses:
        pol = twitter_to_pol[status['user']['screen_name'].lower()]
        date = datetime.date.fromtimestamp(
            email.utils.mktime_tz(
                email.utils.parsedate_tz(status['created_at'])
            )
        ) # fuck you, time formats
        guid = 'twit_%s' % status['id']
        activity.save_activity({'text': status['text']}, politician=pol,
            date=date, guid=guid, variety='twitter')
        
    