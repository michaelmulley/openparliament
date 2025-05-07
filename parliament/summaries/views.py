from django.core.mail import mail_admins
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.generic import View

from parliament.core.utils import get_client_ip
from parliament.summaries.models import Summary, SummaryPoll

class SummaryPollView(View):
    def post(self, request):
        summary_id = request.POST.get('summary_id')
        try:
            summary = Summary.objects.get(id=summary_id)
        except Summary.DoesNotExist:
            return HttpResponseBadRequest('Invalid summary ID')
        try:
            vote = int(request.POST.get('vote'))
        except ValueError:
            return HttpResponseBadRequest('Vote is required')
        ip = get_client_ip(request)
        if not SummaryPoll.objects.filter(summary=summary, user_ip=ip).exists():
            SummaryPoll.objects.create(summary=summary, vote=vote, user_ip=ip, user_agent=request.META['HTTP_USER_AGENT'][:250])
        return HttpResponse('OK')
    
summary_poll = SummaryPollView.as_view()

class SummaryFeedbackView(View):
    def post(self, request):
        summary_id = request.POST.get('summary_id')
        try:
            summary = Summary.objects.get(id=summary_id)
        except Summary.DoesNotExist:
            return HttpResponseBadRequest('Invalid summary ID')
        feedback = request.POST.get('feedback')
        if not feedback:
            return HttpResponseBadRequest('Feedback is required')
        mail_admins(
            subject=f"Summary feedback for {summary}",
            message=f"Feedback: {feedback}\nVote: {request.POST.get('vote')}\nDescription: {request.POST.get('description')}",
            fail_silently=True,
        )
        return HttpResponse('OK')
summary_feedback = SummaryFeedbackView.as_view()