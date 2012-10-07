import json
import re
from urllib import urlencode

from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, Http404
from django.middleware.cache import FetchFromCacheMiddleware as DjangoFetchFromCacheMiddleware
from django.shortcuts import render
from django.views.generic import View

from tastypie.paginator import Paginator
from webob.acceptparse import Accept

class APIView(View):

    # Set this to True to allow JSONP (cross-domain) requests
    allow_jsonp = False

    # The list of formats should be ordered by preferability
    formats = [
        ('html', 'text/html'),
        ('json', 'application/json'),
        ('apibrowser', 'text/html'),
    ]

    # By default, if the Accept header doesn't match anything
    # we can provide, raise HTTP 406 Not Acceptable.
    # Alternatively, set this to a mimetype to be used
    # if there's no intersection between the Accept header
    # and our options.
    default_mimetype = None

    def __init__(self, *args, **kwargs):
        super(APIView, self).__init__(*args, **kwargs)

        if hasattr(self, 'get_json'):
            self.get_apibrowser = self.get_json

        self.available_methods = dict()
        self.MIMETYPE_LOOKUP = dict()
        for m in self.http_method_names:
            for f, mime in self.formats:
                if hasattr(self, '_'.join((m, f))):
                    self.available_methods.setdefault(m, set()).add(f)
                    self.MIMETYPE_LOOKUP.setdefault(mime, f)

    def get_request_format(self, request, available_formats):
        if request.GET.get('format') in available_formats:
            return request.GET['format']
        elif request.GET.get('format'):
            return None

        mimetype = Accept(request.META.get('HTTP_ACCEPT', 'text/html')).best_match(
            [f[1] for f in self.formats if f[0] in available_formats],
            default_match=self.default_mimetype
        )
        return self.MIMETYPE_LOOKUP[mimetype] if mimetype else None

    def dispatch(self, request, **kwargs):
        self.request = request
        self.kwargs = kwargs

        method = request.method.lower()

        if method not in self.available_methods:
            return self.http_method_not_allowed(request)

        available_formats = self.available_methods[method]
        format = self.get_request_format(request, available_formats)
        if not format:
            return self.format_not_allowed(request)

        if format != 'apibrowser' and 'apibrowser' in available_formats:
            params = dict([k, v.encode('utf-8')] for k,v in request.GET.items())
            params['format'] = 'apibrowser'
            request.apibrowser_url = '?' + urlencode(params)

        handler = getattr(self, '_'.join((method, format)))
        result = handler(request, **kwargs)

        processor = getattr(self, 'process_' + format, self.process_default)
        return processor(result, request, **kwargs)

    def format_not_allowed(self, request):
        msg = u'This resource is only available in ' + ', '.join(
            set([f[1] for f in self.formats if f[0] == ff][0] 
                for ff in self.available_methods[request.method.lower()]))
        return HttpResponse(msg, content_type='text/plain', status=406)

    def process_default(self, result, request, **kwargs):
        return result

    def process_json(self, result, request, **kwargs):
        if isinstance(result, HttpResponse):
            return result
        
        pretty_print = (kwargs.pop('pretty_print')
            if kwargs.get('pretty_print') is not None
            else request.GET.get('indent'))

        resp = HttpResponse(content_type='application/json')
        callback = ''
        if self.allow_jsonp and 'callback' in request.GET:
            callback = re.sub(r'[^a-zA-Z0-9_]', '', request.GET['callback'])
            resp.write(callback + '(')
        json.dump({'status': 'ok', 'content': result}, resp,
            indent=4 if pretty_print else None)
        if callback:
            resp.write(');')

        return resp

    def process_apibrowser(self, result, request, **kwargs):
        kwargs['pretty_print'] = True
        content = self.process_json(result, request, **kwargs).content
        title = u'API'
        if getattr(self, 'resource_name', None):
            title += u': ' + self.resource_name
        ctx = dict(
            json=content,
            title=title
        )
        return render(request, 'api/browser.html', ctx)

    def _allowed_methods(self):
        return [m.upper() for m in self.available_methods]


class JSONView(APIView):

    default_mimetype = 'application/json'

    def __init__(self, *args, **kwargs):
        # Make self.get_json == self.get
        for meth in self.http_method_names:
            if hasattr(self, meth):
                setattr(self, meth + '_json', getattr(self, meth))
        super(JSONView, self).__init__(*args, **kwargs)


class ModelListView(APIView):

    filter_types = ['exact', 'iexact', 'contains', 'icontains',
        'startswith', 'istartswith', 'endswith', 'iendswith', 'isnull']

    default_limit = 20
    
    def object_to_dict(self, obj):
        return obj.to_api_dict(representation='list')

    def get_qs(self, request, **kwargs):
        return self.model._default_manager.all()

    def filter(self, request, qs):
        for (f, val) in request.GET.items():
            if '__' in f:
                (filter_field, filter_type) = f.split('__')
            else:
                (filter_field, filter_type) = (f, 'exact')
            if filter_field in getattr(self, 'filterable_fields', []) and filter_type in self.filter_types:
                if val in ['true', 'True']:
                    val = True
                elif val in ['false', 'False']:
                    val = False
                qs = qs.filter(**{filter_field + '__' + filter_type: val})
        return qs

    def get_json(self, request, **kwargs):
        qs = self.get_qs(request, **kwargs)
        qs = self.filter(request, qs)

        paginator = Paginator(request.GET, qs, resource_uri=request.path, limit=self.default_limit)
        result = paginator.page()
        result['objects'] = [self.object_to_dict(obj) for obj in result['objects']]
        return result


class ModelDetailView(APIView):

    def object_to_dict(self, obj):
        return obj.to_api_dict(representation='detail')

    def get_json(self, request, **kwargs):
        try:
            obj = self.get_object(request, **kwargs)
        except ObjectDoesNotExist:
            raise Http404
        return self.object_to_dict(obj)

class FetchFromCacheMiddleware(DjangoFetchFromCacheMiddleware):
    # Our API resources have the same URL as HTML resources,
    # and we use Accept header negotiation to determine what to respond with.
    # The clean way of dealing with this at the cache layer is to add Vary: Accept
    # to our responses, and both Django's cache middleware and any well-behaved
    # upstream caches should work fine. But that will also cache separate versions
    # of the page for any given Accept: header, which could significantly reduce
    # the performance of the cache.
    # 
    # So we take the hacky approach of disabling our cache if the string 'json'
    # appears in the Accept header.

    def process_request(self, request):
        if 'json' in request.META.get('HTTP_ACCEPT', ''):
            request._cache_update_cache = False
            return None
        return super(FetchFromCacheMiddleware, self).process_request(request)