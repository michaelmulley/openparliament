from copy import copy

from django.conf.urls.defaults import url

from tastypie import fields
from tastypie.api import Api
from tastypie.constants import ALL, ALL_WITH_RELATIONS
from tastypie.http import *
from tastypie.resources import ModelResource

from parliament.core.models import Politician, ElectedMember, \
    Party, Riding, Session
from parliament.bills.models import Bill, VoteQuestion


class BaseResource(ModelResource):
    def dispatch_custom(self, request, **kwargs):
        return self.dispatch('custom', request, **kwargs)


class PartyResource(ModelResource):
    class Meta:
        resource_name = 'parties'
        queryset = Party.objects.all()


class RidingResource(ModelResource):
    class Meta:
        resource_name = 'ridings'
        queryset = Riding.objects.all()


class ElectedMemberResource(ModelResource):
    party = fields.ToOneField(PartyResource, 'party', full=True)
    riding = fields.ToOneField(RidingResource, 'riding', full=True)
    politician = fields.ToOneField(
        'parliament.api.v1.PoliticianResource',
        'politician'
    )

    class Meta:
        resource_name = 'electedmembers'
        queryset = ElectedMember.objects.all().select_related('party')


class PoliticianResource(BaseResource):
    elected_members = fields.ToManyField(
        ElectedMemberResource,
        'electedmember_set',
        full=True
    )
    info = fields.ApiField('info_multivalued')
    public_url = fields.CharField(attribute='get_absolute_url')

    class Meta:
        resource_name = 'politicians'
        queryset = Politician.objects.elected()  # elected?
        fields = ('name', 'gender', 'id')
        custom_allowed_methods = ['get']

    def override_urls(self):
        return [url(
            r"^(?P<resource_name>%s)/parliament_id/(?P<parl_id>\d+)/$" \
                % self._meta.resource_name,
            self.wrap_view('dispatch_custom')
        ), ]

    def get_custom(self, request, **kwargs):
        if 'parl_id' in kwargs:
            try:
                obj = Politician.objects.get_by_parl_id(
                    int(kwargs['parl_id'])
                )
            except Politician.DoesNotExist:
                return HttpNotFound()
            bundle = self.full_dehydrate(obj)
            return self.create_response(request, bundle)
        return HttpNotFound()


class SessionResource(ModelResource):
    class Meta:
        resource_name = 'sessions'
        queryset = Session.objects.all()


class VoteQuestionResource(ModelResource):
    public_url = fields.CharField(attribute='get_absolute_url')

    class Meta:
        resource_name = 'votequestions'
        queryset = VoteQuestion.objects.all()

    def override_urls(self):
        # Use e.g. votequestions/40-3/100/ as our URLS
        return [url(
            r"^(?P<resource_name>%s)/" \
            "(?P<session>\d+-\d)/(?P<number>\d+)/$" \
            % self._meta.resource_name,
            self.wrap_view('dispatch_detail'),
            name="api_dispatch_detail"
        ), ]


class BillResource(ModelResource):
    sessions = fields.ToManyField(SessionResource, 'sessions')
    votequestions = fields.ToManyField(
        VoteQuestionResource,
        'votequestion_set'
    )
    public_url = fields.CharField(attribute='get_absolute_url')

    class Meta:
        filtering = {
            'sessions': ALL,
            'law': ALL,
            'privatemember': ALL,
            'institution': ALL
        }
        resource_name = 'bills'
        queryset = Bill.objects.all()

api_v1 = Api(api_name='beta')
#api_beta = copy(api_v1)
#api_beta.api_name = 'v1'
api_v1.register(PoliticianResource())
api_v1.register(ElectedMemberResource())
api_v1.register(PartyResource())
api_v1.register(RidingResource())
api_v1.register(SessionResource())
api_v1.register(BillResource())
api_v1.register(VoteQuestionResource())
