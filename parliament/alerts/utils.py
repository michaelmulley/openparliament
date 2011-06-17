from collections import defaultdict

from django.template import Context, loader, RequestContext
from django.core.mail import send_mail

from parliament.alerts.models import PoliticianAlert
from parliament.core.templatetags.ours import english_list

import logging
logger = logging.getLogger(__name__)

def alerts_for_hansard(hansard):
    alerts = PoliticianAlert.public.all()
    alert_set = set([alert.politician_id for alert in alerts])
    
    statements = defaultdict(list)
    topics = defaultdict(list)
    for statement in hansard.statement_set.filter(speaker=False):
        pol_id = statement.politician_id
        if pol_id in alert_set:
            statements[pol_id].append(statement)
            if statement.topic not in topics[pol_id]:
                topics[pol_id].append(statement.topic)
            
    for alert in alerts:
        pol_id = alert.politician_id
        if statements[pol_id]:
            pol = alert.politician
            c = Context({
                'alert': alert,
                'statements': statements[pol_id],
                'topics': topics[pol_id]
            })
            t = loader.get_template("alerts/politician.txt")
            msg = t.render(c)
            subj = u'%(politician)s spoke about %(topics)s in the House' % {
                'politician': pol.name,
                'topics': english_list(topics[pol_id])
            }
            subj = subj[:200]
            try:
                send_mail(subject=subj,
                    message=msg,
                    from_email='alerts@contact.openparliament.ca',
                    recipient_list=[alert.email])
            except Exception as e:
                logger.error("Error sending alert %s; %r" % (alert.id, e))

def clear_former_mp_alerts(qs=None):
    from parliament.core.models import ElectedMember

    if qs is None:
        qs = PoliticianAlert.objects.filter(active=True)
    bad_alerts = [a for a in qs
        if not a.politician.current_member]
    for alert in bad_alerts:
        riding = alert.politician.latest_member.riding
        new_politician = ElectedMember.objects.get(riding=riding, end_date__isnull=True).politician
        t = loader.get_template("alerts/former_mp.txt")
        c = Context({
            'politician': alert.politician,
            'riding': riding,
            'new_politician': new_politician
        })
        msg = t.render(c)
        subj = u'Your alerts for %s from openparliament.ca' % alert.politician.name
        try:
            send_mail(subject=subj,
                message=msg,
                from_email='alerts@contact.openparliament.ca',
                recipient_list=[alert.email])
            alert.active = False
            alert.save()
        except Exception as e:
            logger.error("Couldn't send mail for alert %s; %r" % (alert.id, e))
