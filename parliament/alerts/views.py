import re

from django.template import loader, RequestContext
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, render
from django import forms
from django.conf import settings
from django.core import urlresolvers
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail, mail_admins
from django.core.signing import Signer, TimestampSigner, BadSignature
from django.views.decorators.cache import never_cache

from parliament.accounts.models import User
from parliament.alerts.models import PoliticianAlert, Subscription
from parliament.core.models import Politician
from parliament.core.views import disable_on_readonly_db
from parliament.utils.views import JSONView

class PoliticianAlertForm(forms.Form):

    email = forms.EmailField(label='Your email')
    politician = forms.IntegerField(widget=forms.HiddenInput)

@disable_on_readonly_db
def politician_hansard_signup(request):
    try:
        politician_id = int(re.sub(r'\D', '', request.REQUEST.get('politician', '')))
    except ValueError:
        raise Http404
    
    pol = get_object_or_404(Politician, pk=politician_id)
    success = False
    if request.method == 'POST':
        # This is a hack to remove spaces from e-mails before sending them off to the validator
        # If anyone knows a cleaner way of doing this without writing a custom field, please let me know
        postdict = request.POST.copy()
        if 'email' in postdict:
            postdict['email'] = postdict['email'].strip().lower()
            
        form = PoliticianAlertForm(postdict)
        if form.is_valid():
            key = "%s,%s" % (politician_id, form.cleaned_data['email'])
            signed_key = TimestampSigner(salt='alerts_pol_subscribe').sign(key)
            activate_url = urlresolvers.reverse('alerts_pol_subscribe',
                kwargs={'signed_key': signed_key})
            activation_context = RequestContext(request, {
                'pol': pol,
                'activate_url': activate_url,
            })
            t = loader.get_template("alerts/activate.txt")
            send_mail(subject=u'Confirmation required: Email alerts about %s' % pol.name,
                message=t.render(activation_context),
                from_email='alerts@contact.openparliament.ca',
                recipient_list=[form.cleaned_data['email']])
            
            success = True
    else:
        form = PoliticianAlertForm(initial={'politician': politician_id})
        
    c = RequestContext(request, {
        'form': form,
        'success': success,
        'pol': pol,
        'title': 'Email alerts for %s' % pol.name,
    })
    t = loader.get_template("alerts/signup.html")
    return HttpResponse(t.render(c))


@never_cache
def alerts_list(request):
    if not request.authenticated_email:
        return render(request, 'alerts/list_unauthenticated.html',
            {'title': 'Email alerts'})

    user = User.objects.get(email=request.authenticated_email)

    if request.session.get('pending_alert'):
        Subscription.objects.get_or_create_by_query(request.session['pending_alert'], user)
        del request.session['pending_alert']

    subscriptions = Subscription.objects.filter(user=user).select_related('topic')

    t = loader.get_template('alerts/list.html')
    c = RequestContext(request, {
        'user': user,
        'subscriptions': subscriptions,
        'title': 'Your email alerts'
    })
    resp = HttpResponse(t.render(c))
    resp.set_cookie(
        key='enable-alerts',
        value='y',
        max_age=60*60*24*90,
        httponly=False
    )
    return resp


class CreateAlertView(JSONView):

    def post(self, request):
        query = request.POST.get('query')
        if not query:
            raise Http404
        user_email = request.authenticated_email
        if not user_email:
            request.session['pending_alert'] = query
            return self.redirect(urlresolvers.reverse('alerts_list'))
        user = User.objects.get(email=user_email)
        try:
            subscription = Subscription.objects.get_or_create_by_query(query, user)
            return True
        except ValueError:
            raise NotImplementedError
create_alert = CreateAlertView.as_view()


class ModifyAlertView(JSONView):

    def post(self, request, subscription_id):
        subscription = get_object_or_404(Subscription, id=subscription_id)
        if subscription.user.email != request.authenticated_email:
            raise PermissionDenied

        action = request.POST.get('action')
        if action == 'enable':
            subscription.active = True
            subscription.save()
        elif action == 'disable':
            subscription.active = False
            subscription.save()
        elif action == 'delete':
            subscription.delete()

        return True
modify_alert = ModifyAlertView.as_view()

@disable_on_readonly_db
def politician_hansard_subscribe(request, signed_key):
    try:
        key = TimestampSigner(salt='alerts_pol_subscribe').unsign(signed_key, max_age=60*60*24*14)
        key_error = False
        politician_id, _, email = key.partition(',')
        pol = get_object_or_404(Politician, id=politician_id)
        if not pol.current_member:
            raise Http404

        user, created = User.objects.get_or_create(email=email)
        query = u'MP: "%s" Type: "debate"' % pol.identifier
        sub, created = Subscription.objects.get_or_create_by_query(query, user)
        if not sub.active:
            sub.active = True
            sub.save()
    except BadSignature:
        key_error = True

    return render(request, 'alerts/activate.html', {
        'pol': pol,
        'title': u'Email alerts for %s' % pol.name,
        'activating': True,
        'key_error': key_error,
    })


@never_cache
def unsubscribe(request, key):
    ctx = {
        'title': 'Email alerts'
    }
    try:
        subscription_id = Signer(salt='alerts_unsubscribe').unsign(key)
        subscription = get_object_or_404(Subscription, id=subscription_id)
        subscription.active = False
        subscription.save()
        if settings.PARLIAMENT_DB_READONLY:
            mail_admins("Unsubscribe request", subscription_id)
        ctx['query'] = subscription.topic
    except BadSignature:
        ctx['key_error'] = True
    c = RequestContext(request, ctx)
    t = loader.get_template("alerts/unsubscribe.html")
    return HttpResponse(t.render(c))


def unsubscribe_old(request, alert_id, key):
    alert = get_object_or_404(PoliticianAlert, pk=alert_id)
    
    correct_key = alert.get_key()
    if correct_key != key:
        key_error = True
    else:
        key_error = False
        alert.active = False
        alert.save()
        if settings.PARLIAMENT_DB_READONLY:
            mail_admins("Unsubscribe request", alert_id)
        
    c = RequestContext(request, {
        'pol': alert.politician,
        'query': alert.politician.name,
        'title': u'E-mail alerts for %s' % alert.politician.name,
        'key_error': key_error,
    })
    t = loader.get_template("alerts/unsubscribe.html")
    return HttpResponse(t.render(c))
    
    