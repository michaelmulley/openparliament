import json
import re
from urllib import urlencode

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, Http404
from django.middleware.cache import FetchFromCacheMiddleware as DjangoFetchFromCacheMiddleware
from django.shortcuts import render
from django.views.generic import View

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
            params = dict([k, v.encode('utf-8')] for k, v in request.GET.items())
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
        if not isinstance(result, dict):
            result = {'content': result}
        json.dump(result, resp, indent=4 if pretty_print else None)
        if callback:
            resp.write(');')

        return resp

    def process_apibrowser(self, result, request, **kwargs):
        if isinstance(result, HttpResponse):
            return result

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
        d = obj.to_api_dict(representation='list')
        if 'url' not in d:
            d['url'] = obj.get_absolute_url()
        return d

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

        paginator = APIPaginator(request, qs, limit=self.default_limit)
        (objects, page_data) = paginator.page()
        result = dict(
            objects=[self.object_to_dict(obj) for obj in objects],
            pagination=page_data
        )
        related = self.get_related_resources(request, qs, result)
        if related:
            result['related'] = related
        return result

    def get_related_resources(self, request, qs, result):
        return None


class ModelDetailView(APIView):

    def object_to_dict(self, obj):
        d = obj.to_api_dict(representation='detail')
        if 'url' not in d:
            d['url'] = obj.get_absolute_url()
        return d

    def get_json(self, request, **kwargs):
        try:
            obj = self.get_object(request, **kwargs)
        except ObjectDoesNotExist:
            raise Http404
        result = dict(object=self.object_to_dict(obj))
        related = self.get_related_resources(request, obj, result)
        if related:
            result['related'] = related
        return result

    def get_related_resources(self, request, obj, result):
        return None


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


class BadRequest(Exception):
    pass


class APIPaginator(object):
    """
    Largely cribbed from django-tastypie.
    """
    def __init__(self, request, objects, limit=None, offset=0, max_limit=500):
        """
        Instantiates the ``Paginator`` and allows for some configuration.

        The ``objects`` should be a list-like object of ``Resources``.
        This is typically a ``QuerySet`` but can be anything that
        implements slicing. Required.

        Optionally accepts a ``limit`` argument, which specifies how many
        items to show at a time. Defaults to ``None``, which is no limit.

        Optionally accepts an ``offset`` argument, which specifies where in
        the ``objects`` to start displaying results from. Defaults to 0.
        """
        self.request_data = request.GET
        self.objects = objects
        self.limit = limit
        self.max_limit = max_limit
        self.offset = offset
        self.resource_uri = request.path

    def get_limit(self):
        """
        Determines the proper maximum number of results to return.

        In order of importance, it will use:

            * The user-requested ``limit`` from the GET parameters, if specified.
            * The object-level ``limit`` if specified.
            * ``settings.API_LIMIT_PER_PAGE`` if specified.

        Default is 20 per page.
        """
        settings_limit = getattr(settings, 'API_LIMIT_PER_PAGE', 20)

        if 'limit' in self.request_data:
            limit = self.request_data['limit']
        elif self.limit is not None:
            limit = self.limit
        else:
            limit = settings_limit

        try:
            limit = int(limit)
        except ValueError:
            raise BadRequest("Invalid limit '%s' provided. Please provide a positive integer." % limit)

        if limit == 0:
            if self.limit:
                limit = self.limit
            else:
                limit = settings_limit

        if limit < 0:
            raise BadRequest("Invalid limit '%s' provided. Please provide a positive integer >= 0." % limit)

        if self.max_limit and limit > self.max_limit:
            return self.max_limit

        return limit

    def get_offset(self):
        """
        Determines the proper starting offset of results to return.

        It attempst to use the user-provided ``offset`` from the GET parameters,
        if specified. Otherwise, it falls back to the object-level ``offset``.

        Default is 0.
        """
        offset = self.offset

        if 'offset' in self.request_data:
            offset = self.request_data['offset']

        try:
            offset = int(offset)
        except ValueError:
            raise BadRequest("Invalid offset '%s' provided. Please provide an integer." % offset)

        if offset < 0:
            raise BadRequest("Invalid offset '%s' provided. Please provide a positive integer >= 0." % offset)

        return offset

    def _generate_uri(self, limit, offset):
        if self.resource_uri is None:
            return None

        # QueryDict has a urlencode method that can handle multiple values for the same key
        request_params = self.request_data.copy()
        if 'limit' in request_params:
            del request_params['limit']
        if 'offset' in request_params:
            del request_params['offset']
        request_params.update({'limit': limit, 'offset': max(offset, 0)})
        encoded_params = request_params.urlencode()

        return '%s?%s' % (
            self.resource_uri,
            encoded_params
        )

    def page(self):
        """
        Returns a tuple of (objects, page_data), where objects is one page of objects (a list),
        and page_data is a dict of pagination info.
        """
        limit = self.get_limit()
        offset = self.get_offset()

        page_data = {
            'offset': offset,
            'limit': limit,
        }

        # We get one more object than requested, to see if
        # there's a next page.
        objects = list(self.objects[offset:offset + limit + 1])
        if len(objects) > limit:
            objects.pop()
            page_data['next'] = self._generate_uri(limit, offset + limit)
        else:
            page_data['next'] = None

        page_data['previous'] = (self._generate_uri(limit, offset - limit)
            if offset > 0 else None)

        return (objects, page_data)
