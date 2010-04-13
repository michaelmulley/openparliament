from collections import defaultdict

from django.template import Context, loader, RequestContext
from django.core.mail import send_mail

from parliament.alerts.models import PoliticianAlert
from parliament.core.templatetags.ours import english_list

def alerts_for_hansard(hansard):
    alerts = PoliticianAlert.objects.all()
    alert_set = set([alert.politician_id for alert in alerts])
    
    statements = defaultdict(list)
    topics = defaultdict(list)
    for statement in hansard.statement_set.all():
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
                    from_email='alerts@openparliament.ca',
                    recipient_list=[alert.email])
            except Exception, e:
                # FIXME logging
                print "Error sending alert %s" % alert.id
                print e
        