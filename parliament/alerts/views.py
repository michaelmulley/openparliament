import hashlib
import base64
import urllib

from django.template import Context, loader, RequestContext
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404
from django import forms
from django.conf import settings
from django.core import urlresolvers
from django.core.mail import send_mail

from parliament.alerts.models import PoliticianAlert
from parliament.core.models import Politician

class PoliticianAlertForm(forms.ModelForm):
    
    class Meta:
        model = PoliticianAlert
        fields = ('email', 'politician')
        widgets = {
            'politician': forms.widgets.HiddenInput,
        }

def signup(request):
    if 'politician' not in request.REQUEST:
        raise Http404
    
    pol = get_object_or_404(Politician, pk=request.REQUEST['politician'])
    success = False
    if request.method == 'POST':
        # This is a hack to remove spaces from e-mails before sending them off to the validator
        # If anyone knows a cleaner way of doing this without writing a custom field, please let me know
        postdict = request.POST.copy()
        if 'email' in postdict:
            postdict['email'] = postdict['email'].strip()
            
        form = PoliticianAlertForm(postdict)
        if form.is_valid():
            try:
                alert = PoliticianAlert.objects.get(email=form.cleaned_data['email'], politician=form.cleaned_data['politician'])
            except PoliticianAlert.DoesNotExist:
                alert = form.save()
            
            key = alert.get_key()
            activate_url = urlresolvers.reverse('parliament.alerts.views.activate',
                kwargs={'alert_id': alert.id, 'key': key}) 
            activation_context = RequestContext(request, {
                'pol': pol,
                'alert': alert,
                'activate_url': activate_url,
            })
            t = loader.get_template("alerts/activate.txt")
            send_mail(subject=u'Confirmation required: E-mail alerts about %s' % pol.name,
                message=t.render(activation_context),
                from_email='alerts@openparliament.ca',
                recipient_list=[alert.email])
            
            success = True
    else:
        form = PoliticianAlertForm(initial={'politician': request.GET['politician']})
        
    c = RequestContext(request, {
        'form': form,
        'success': success,
        'pol': pol,
        'title': 'E-mail alerts for %s' % pol.name,
    })
    t = loader.get_template("alerts/signup.html")
    return HttpResponse(t.render(c))
    
def activate(request, alert_id, key):
    
    alert = get_object_or_404(PoliticianAlert, pk=alert_id)
    
    correct_key = alert.get_key()
    if correct_key != key:
        key_error = True
    else:
        key_error = False
        alert.active = True
        alert.save()
        
    c = RequestContext(request, {
        'pol': alert.politician,
        'title': 'E-mail alerts for %s' % alert.politician.name,
        'activating': True,
        'key_error': key_error
    })
    t = loader.get_template("alerts/activate.html")
    return HttpResponse(t.render(c))
    
def unsubscribe(request, alert_id, key):
    alert = get_object_or_404(PoliticianAlert, pk=alert_id)
    
    correct_key = alert.get_key()
    if correct_key != key:
        key_error = True
    else:
        key_error = False
        alert.active = False
        alert.save()
        
    c = RequestContext(request, {
        'pol': alert.politician,
        'title': 'E-mail alerts for %s' % alert.politician.name,
        'key_error': key_error,
    })
    t = loader.get_template("alerts/unsubscribe.html")
    return HttpResponse(t.render(c))
    
    