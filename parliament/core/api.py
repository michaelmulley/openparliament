import json
import re

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import HttpResponse, Http404, HttpResponseBadRequest
from django.middleware.cache import FetchFromCacheMiddleware as DjangoFetchFromCacheMiddleware
from django.shortcuts import render
from django.utils.html import escape
from django.views.generic import View

from webob.acceptparse import MIMEAccept


class APIView(View):

    # Set this to True to allow JSONP (cross-domain) requests
    allow_jsonp = False

    # Set to False to disallow CORS on GET requests, and the origin to allow otherwise
    allow_cors = '*'

    # Temporary: will need to write an actual versioning system once we want to start
    # preserving backwards compatibility
    api_version = 'v1'

    # The list of API formats should be ordered by preferability
    api_formats = [
        ('apibrowser', 'text/html'),
        ('json', 'application/json')
    ]

    # By default, if the Accept header doesn't match anything
    # we can provide, raise HTTP 406 Not Acceptable.
    # Alternatively, set this to a mimetype to be used
    # if there's no intersection between the Accept header
    # and our options.
    default_mimetype = 'application/json'

    resource_type = ''

    def __init__(self, *args, **kwargs):
        super(APIView, self).__init__(*args, **kwargs)

        if hasattr(self, 'get_json'):
            self.get_apibrowser = self.get_json

        self._formats_list = [f[0] for f in self.api_formats]
        self._mimetype_lookup = dict(
            (f[1], f[0]) for f in self.api_formats
        )

    def get_api_format(self, request):
        if request.GET.get('format') in self._formats_list:
            return request.GET['format']
        elif request.GET.get('format'):
            return None

        mimetype = MIMEAccept(request.META.get('HTTP_ACCEPT', 'application/json')).best_match(
            [f[1] for f in self.api_formats],
            default_match=self.default_mimetype
        )
        return self._mimetype_lookup[mimetype] if mimetype else None

    def dispatch(self, request, **kwargs):
        self.request = request
        self.kwargs = kwargs

        method = request.method.lower()

        request.api_request = (request.get_host().lower().startswith(settings.PARLIAMENT_API_HOST)
                              or request.GET.get('format'))

        if request.api_request:
            format = self.get_api_format(request)
            if not format:
                return self.format_not_allowed(request)
        else:
            # No format negotiation on non-API requests
            format = 'html'

            if hasattr(self, 'get_json'):
                request.apibrowser_url = '//' + settings.PARLIAMENT_API_HOST + request.path

        handler = getattr(self, '_'.join((method, format)), None)
        if handler is None:
            if method == 'get':
                return self.format_not_allowed(request)
            return self.http_method_not_allowed(request)
        try:
            result = handler(request, **kwargs)
        except BadRequest as e:
            return HttpResponseBadRequest(escape(str(e)), content_type='text/plain')

        processor = getattr(self, 'process_' + format, self.process_default)
        resp = processor(result, request, **kwargs)

        if self.allow_cors and method == 'get' and request.META.get('HTTP_ORIGIN'):
            # CORS
            resp['Access-Control-Allow-Origin'] = self.allow_cors

        resp['API-Version'] = self.api_version

        return resp

    def format_not_allowed(self, request):
        return HttpResponse("This resource is not available in the requested format.",
            content_type='text/plain', status=406)

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
        content = self.process_json(result, request, **kwargs).content.decode('utf8')
        resource_name = getattr(self, 'resource_name', None)
        title = resource_name if resource_name else 'API'
        params = request.GET.copy()
        params['format'] = 'json'
        filters = [
            (f, getattr(self.filters[f], 'help', ''))
            for f in sorted(getattr(self, 'filters', {}).keys())
        ]
        ctx = dict(
            json=content,
            title=title,
            filters=filters,
            resource_name=resource_name,
            resource_type=self.resource_type,
            raw_json_url='?' + params.urlencode(),
            notes=getattr(self, 'api_notes', None)
        )
        if hasattr(self, 'get_html'):
            ctx['main_site_url'] = settings.SITE_URL + request.path
        return render(request, 'api/browser.html', ctx)


class APIFilters(object):

    string_filters = ['exact', 'iexact', 'contains', 'icontains',
        'startswith', 'istartswith', 'endswith', 'iendswith']

    numeric_filters = ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull', 'range']

    @staticmethod
    def dbfield(field_name=None, filter_types=['exact'], help=None):
        """Returns a filter function for a standard database query."""
        def inner(qs, view, filter_name, filter_extra, val):
            if not filter_extra:
                filter_extra = 'exact'
            if filter_extra not in filter_types:
                raise BadRequest("Invalid filter argument %s" % filter_extra)
            if val in ['true', 'True']:
                val = True
            elif val in ['false', 'False']:
                val = False
            elif val in ['none', 'None', 'null']:
                val = None
            if filter_extra == 'range':
                val = val.split(',')
            try:
                return qs.filter(**{
                    (field_name if field_name else filter_name) + '__' + filter_extra: val
                })
            except (ValueError, ValidationError) as e:
                raise BadRequest(str(e))
        inner.help = help
        return inner

    @staticmethod
    def fkey(query_func, help=None):
        """Returns a filter function for a foreign-key field.
        The required argument is a function that takes an array 
        (the filter value split by '/'), and returns a dict of the ORM filters to apply.
        So a foreign key to a bill could accept an argument like
            "/bills/41-1/C-50"
        and query_func would be lambda u: {'bill__session': u[-2], 'bill__number': u[-1]}
        """
        def inner(qs, view, filter_name, filter_extra, val):
            url_bits = val.rstrip('/').split('/')
            try:
                return qs.filter(**(query_func(url_bits)))
            except ValueError as e:
                raise BadRequest(e)
        inner.help = help
        return inner

    @staticmethod
    def politician(field_name='politician'):
        return APIFilters.fkey(lambda u: ({field_name: u[-1]} if u[-1].isdigit()
            else {field_name + '__slug': u[-1]}),
            help="e.g. /politicians/tony-clement/")

    @staticmethod
    def choices(field_name, model):
        """Returns a filter function for a database field with defined choices;
        the filter will work whether provided the internal DB value or the display
        value."""
        choices = model._meta.get_field(field_name).choices
        def inner(qs, view, filter_name, filter_extra, val):
            try:
                search_val = next(c[0] for c in choices
                    if val in c)
            except StopIteration:
                raise BadRequest("Invalid value for %s" % filter_name)
            return qs.filter(**{field_name: search_val})
        inner.help = ', '.join(c[1] for c in choices)
        return inner

    @staticmethod
    def noop(help=None):
        """Returns a filter function that does nothing. Useful for when you want
        something to show up in autogenerated docs but are handling it elsewhere,
        e.g. by subclassing the main filter() method."""
        def inner(qs, view, filter_name, filter_extra, val):
            return qs
        inner.help = help
        return inner


class ModelListView(APIView):

    default_limit = 20

    resource_type = 'list'
    
    def object_to_dict(self, obj):
        d = obj.to_api_dict(representation='list')
        if 'url' not in d:
            d['url'] = obj.get_absolute_url()
        return d

    def get_qs(self, request, **kwargs):
        return self.model._default_manager.all()

    def filter(self, request, qs):
        for (f, val) in list(request.GET.items()):
            if val:
                filter_name, _, filter_extra = f.partition('__')
                if filter_name in getattr(self, 'filters', {}):
                    qs = self.filters[filter_name](qs, self, filter_name, filter_extra, val)
        return qs

    def get_json(self, request, **kwargs):
        try:
            qs = self.get_qs(request, **kwargs)
        except ObjectDoesNotExist:
            raise Http404
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

    def get_related_resources(self, request, qs, result) -> dict[str, str] | None:
        return None


class ModelDetailView(APIView):

    resource_type = 'single'

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
        result = self.object_to_dict(obj)
        related = self.get_related_resources(request, obj, result)
        if related:
            result['related'] = related
        return result

    def get_related_resources(self, request, obj, result) -> dict[str, str] | None:
        return None


def no_robots(request):
    host = request.get_host().lower()
    if host.startswith('api.') or host.startswith('op.') or getattr(settings, 'PARLIAMENT_NO_ROBOTS', False):
        return HttpResponse('User-agent: *\nDisallow: /\n', content_type='text/plain')
    return HttpResponse(settings.PARLIAMENT_ROBOTS_TXT, content_type='text/plain')

def docs(request):
    return render(request, 'api/doc.html', {'title': 'API'})


class FetchFromCacheMiddleware(DjangoFetchFromCacheMiddleware):
    # Since API resources are often served from the same URL as
    # main site resources, and we use Accept header negotiation to determine
    # formats, it's not a good fit with the full-site cache middleware.
    # So we'll just disable it for the API.

    def process_request(self, request):
        if request.get_host().lower().startswith(settings.PARLIAMENT_API_HOST):
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
            page_data['next_url'] = self._generate_uri(limit, offset + limit)
        else:
            page_data['next_url'] = None

        page_data['previous_url'] = (self._generate_uri(limit, offset - limit)
            if offset > 0 else None)

        return (objects, page_data)
