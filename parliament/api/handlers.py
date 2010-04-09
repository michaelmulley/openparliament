from piston.handler import BaseHandler
from piston.resource import Resource
from piston.utils import rc, throttle

from parliament.hansards.models import Hansard
from django.core import urlresolvers

class HansardHandler(BaseHandler):
    allowed_methods = ('GET',)   

    @throttle(2, 10*60)
    def read(self, request, hansard_id):
        try:
            hansard = Hansard.objects.get(pk=hansard_id)
        except Hansard.DoesNotExist:
            return rc.NOT_FOUND
        return hansard.serializable()
        
class HansardListHandler(BaseHandler):
    allowed_methods = ('GET',)
    fields = ('date', 'number', 'id', 'api_url')
    
    @classmethod
    def api_url(klass, instance):
        return urlresolvers.reverse('parliament.api.handlers.hansard_resource', kwargs={'hansard_id': instance.id})
        
    def read(self, request):
        return Hansard.objects.all()

hansard_resource = Resource(HansardHandler)
hansardlist_resource = Resource(HansardListHandler)