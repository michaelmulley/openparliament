from django.template import loader
from django.core.mail import send_mail

from parliament.alerts.models import PoliticianAlert

import logging
logger = logging.getLogger(__name__)


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
        c = {
            'politician': alert.politician,
            'riding': riding,
            'new_politician': new_politician
        }
        msg = t.render(c)
        subj = 'Your alerts for %s from openparliament.ca' % alert.politician.name
        try:
            send_mail(subject=subj,
                message=msg,
                from_email='alerts@contact.openparliament.ca',
                recipient_list=[alert.email])
            alert.active = False
            alert.save()
        except Exception as e:
            logger.error("Couldn't send mail for alert %s; %r" % (alert.id, e))
