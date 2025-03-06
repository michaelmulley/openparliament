import datetime
import json
import re

from django.template import loader
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import get_object_or_404, render
from django import forms
from django.conf import settings
from django.contrib import messages
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail, mail_admins
from django.core.signing import Signer, TimestampSigner, BadSignature
from django.views.decorators.cache import never_cache

from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Invisible

from parliament.accounts.models import User
from parliament.alerts.models import Subscription
from parliament.core.models import Politician
from parliament.core.views import disable_on_readonly_db
from parliament.utils.views import JSONView

class PoliticianAlertForm(forms.Form):

    email = forms.EmailField(label='Your email',
        widget=forms.widgets.EmailInput(attrs={'class': 'input-group-field'}))
    politician = forms.IntegerField(widget=forms.HiddenInput)
    captcha = ReCaptchaField(widget=ReCaptchaV2Invisible)

@disable_on_readonly_db
def politician_hansard_signup(request):
    try:
        politician_id = int(re.sub(r'\D', '',
            (request.POST if request.method == 'POST' else request.GET).get('politician', '')))
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
            if form.cleaned_data['email'] == request.authenticated_email:
                Subscription.objects.get_or_create_by_query(
                    _generate_query_for_politician(pol),
                    request.authenticated_email_user
                )
                messages.success(request, "You're signed up for alerts for %s." % pol.name)
                return HttpResponseRedirect(reverse('alerts_list'))

            key = "%s,%s" % (politician_id, form.cleaned_data['email'])
            signed_key = TimestampSigner(salt='alerts_pol_subscribe').sign(key)
            activate_url = reverse('alerts_pol_subscribe',
                kwargs={'signed_key': signed_key})
            activation_context = {
                'pol': pol,
                'activate_url': activate_url,
            }
            t = loader.get_template("alerts/activate.txt")
            send_mail(subject='Confirmation required: Email alerts about %s' % pol.name,
                message=t.render(activation_context, request),
                from_email='alerts@contact.openparliament.ca',
                recipient_list=[form.cleaned_data['email']])

            success = True
    else:
        initial = {
            'politician': politician_id
        }
        if request.authenticated_email:
            initial['email'] = request.authenticated_email
        form = PoliticianAlertForm(initial=initial)
        
    c = {
        'form': form,
        'success': success,
        'pol': pol,
        'title': 'Email alerts for %s' % pol.name,
    }
    t = loader.get_template("alerts/signup.html")
    return HttpResponse(t.render(c, request))


@never_cache
@disable_on_readonly_db
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
    c = {
        'alerts_user': user,
        'subscriptions': subscriptions,
        'title': 'Your email alerts'
    }
    resp = HttpResponse(t.render(c, request))
    # resp.set_cookie(
    #     key='enable-alerts',
    #     value='y',
    #     max_age=60*60*24*90,
    #     httponly=False
    # )
    return resp


class CreateAlertView(JSONView):

    def post(self, request):
        query = request.POST.get('query')
        if not query:
            raise Http404
        user_email = request.authenticated_email
        if not user_email:
            request.session['pending_alert'] = query
            return self.redirect(reverse('alerts_list'))
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

def _generate_query_for_politician(pol):
    return 'MP: "%s" Type: "debate"' % pol.identifier

@disable_on_readonly_db
def politician_hansard_subscribe(request, signed_key):
    ctx = {
        'key_error': False
    }
    try:
        key = TimestampSigner(salt='alerts_pol_subscribe').unsign(signed_key, max_age=60*60*24*90)
        politician_id, _, email = key.partition(',')
        pol = get_object_or_404(Politician, id=politician_id)
        if not pol.current_member:
            raise Http404

        user, created = User.objects.get_or_create(email=email)
        sub, created = Subscription.objects.get_or_create_by_query(
            _generate_query_for_politician(pol), user)
        if not sub.active:
            sub.active = True
            sub.save()
        ctx.update(
            pol=pol,
            title='Email alerts for %s' % pol.name
        )
        if user.email_bouncing:
            mail_admins("bounce flag cleared after new signup", email)
            user.email_bouncing = False
            user.save()
    except BadSignature:
        ctx['key_error'] = True

    return render(request, 'alerts/activate.html', ctx)


@never_cache
def unsubscribe(request, key):
    ctx = {
        'title': 'Email alerts'
    }
    try:
        subscription_id = Signer(salt='alerts_unsubscribe').unsign(key)
        subscription = get_object_or_404(Subscription, id=subscription_id)
        
        if request.method == 'POST':
            # Only unsubscribe on POST request
            if settings.PARLIAMENT_DB_READONLY:
                mail_admins("Unsubscribe request", subscription_id)
            else:
                subscription.active = False
                subscription.save()
            ctx['unsubscribed'] = True
        else:
            ctx['unsubscribed'] = not subscription.active

        ctx['query'] = subscription.topic
        ctx['email'] = subscription.user.email
        ctx['key'] = key
    except BadSignature:
        ctx['key_error'] = True
    t = loader.get_template("alerts/unsubscribe.html")
    return HttpResponse(t.render(ctx, request))


@disable_on_readonly_db
def bounce_webhook(request):
    """
    Simple view to process bounce reports delivered via webhook.
    
    Currently support Mandrill and Amazon SES.
    """
    sns_message_type = request.META.get('HTTP_X_AMZ_SNS_MESSAGE_TYPE')

    if sns_message_type:
        try:
            data = json.loads(json.loads(request.body)['Message'])
            ntype = data['notificationType']
            if ntype == 'Bounce':
                recipients = [b['emailAddress'] for b in data['bounce']['bouncedRecipients']]
            elif ntype == 'Complaint':
                recipients = [b['emailAddress'] for b in data['complaint']['complainedRecipients']]
                mail_admins("SES complaint (%r)" % recipients, json.dumps(data, indent=2))
            else:
                mail_admins("Unhandled SES notification", json.dumps(data, indent=2))
                return HttpResponse('OK')
            
            for recipient in recipients:
                if ntype == 'Bounce' and data['bounce']['bounceType'] in ('Transient', 'Undetermined'):
                    try:
                        user = User.objects.get(email=recipient)
                        user.data.setdefault('transient_bounces', []).append(
                            "{} {}".format(datetime.date.today(), data['bounce']['bounceSubType']))
                        user.save()
                    except User.DoesNotExist:
                        pass
                else:
                    User.objects.filter(email=recipient).update(email_bouncing=True,
                        email_bounce_reason=request.body)
        except KeyError:
            mail_admins("Unhandled SES notification", request.body)
    elif 'mandrill_events' in request.POST:
        for event in json.loads(request.POST['mandrill_events']):
            if 'bounce' in event['event']:
                User.objects.filter(email=event['msg']['email']).update(email_bouncing=True,
                    email_bounce_reason=json.dumps(event))
    else:
        raise Http404

    return HttpResponse('OK')
