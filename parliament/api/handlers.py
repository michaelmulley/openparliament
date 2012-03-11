from piston.handler import BaseHandler
from piston.resource import Resource
from piston.utils import rc, throttle

from parliament.core.models import Politician
from parliament.hansards.models import Document
from django.core import urlresolvers

class HansardHandler(BaseHandler):
    allowed_methods = ('GET',)   

    @throttle(3, 60)
    def read(self, request, hansard_id):
        try:
            hansard = Document.objects.get(pk=hansard_id)
        except Document.DoesNotExist:
            return rc.NOT_FOUND
        return hansard.serializable()
        
class HansardListHandler(BaseHandler):
    allowed_methods = ('GET',)
    fields = ('date', 'number', 'id', 'api_url')
    
    @classmethod
    def api_url(klass, instance):
        return urlresolvers.reverse('parliament.api.handlers.hansard_resource', kwargs={'hansard_id': instance.id})
        
    def read(self, request):
        return Document.objects.all()
        
class PoliticianHandler(BaseHandler):
    allowed_methods = ('GET',)
    fields = ('id', 'gender', 'url', 'info_multivalued', 
        ('electedmember_set', ('start_date', 'end_date', 
            ('riding', ('name', 'edid')),
            ('party', ('name', 'id')))))
    model = Politician
    
    def read(self, request, politician_id=None, callback_id=None):
        try:
            if politician_id:
                return Politician.objects.get(pk=politician_id)
            elif callback_id:
                return Politician.objects.get_by_parl_id(callback_id)
        except Politician.DoesNotExist as e:
            return rc.NOT_FOUND

hansard_resource = Resource(HansardHandler)
hansardlist_resource = Resource(HansardListHandler)
politician_resource = Resource(PoliticianHandler)