import datetime
from hashlib import sha1

from django.conf import settings
from django.template import loader

from parliament.activity.models import Activity

def save_activity(obj, politician, date, guid=None, variety=None):
    if not getattr(settings, 'PARLIAMENT_SAVE_ACTIVITIES', True):
        return
    if not variety:
        variety = obj.__class__.__name__.lower()
    if not guid:
        guid = variety + str(obj.id)
    if len(guid) > 50:
        guid = sha1(guid.encode('utf8')).hexdigest()
    if Activity.objects.filter(guid=guid).exists():
        return False
    t = loader.get_template("activity/%s.html" % variety.lower())
    c = {'obj': obj, 'politician': politician}
    Activity(variety=variety,
        date=date,
        politician=politician,
        guid=guid,
        payload = t.render(c)).save()
    return True

ACTIVITY_MAX = {
    'twitter': 6,
    'gnews': 6,
    'membervote': 5,
    'statement': 8,
    'billsponsor': 7,
    'committee': 8,
} 
def iter_recent(queryset):
    activity_counts = ACTIVITY_MAX.copy()
    for activity in queryset:
        if activity_counts[activity.variety]:
            activity_counts[activity.variety] -= 1
            yield activity
            
def prune(queryset):
    today = datetime.date.today()
    activity_counts = ACTIVITY_MAX.copy()
    for activity in queryset:
        if activity_counts[activity.variety] >= 0:
            activity_counts[activity.variety] -= 1
        elif (today - activity.date).days >= 4: # only start pruning if it's a few days old
            activity.active = False
            activity.save()
        
