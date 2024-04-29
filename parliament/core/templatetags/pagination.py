from django import template

register = template.Library()

# http://djangosnippets.org/snippets/2763/
LEADING_PAGE_RANGE_DISPLAYED = TRAILING_PAGE_RANGE_DISPLAYED = 8
LEADING_PAGE_RANGE = TRAILING_PAGE_RANGE = 6
NUM_PAGES_OUTSIDE_RANGE = 2
ADJACENT_PAGES = 2

@register.simple_tag(takes_context=True)
def foundation_paginator(context):
    ctx = _get_pagination_context(context)
    if not ctx:
        return ''
    return template.loader.get_template("foundation_paginator.html").render(ctx)

def _get_pagination_context(context):
    page_obj = context['page']
    try:
        paginator = page_obj.paginator
    except AttributeError:
        return ''
    pages = paginator.num_pages
    if pages <= 1:
        return ''
    page = page_obj.number
    in_leading_range = in_trailing_range = False
    pages_outside_leading_range = pages_outside_trailing_range = list(range(0))
    if pages <= LEADING_PAGE_RANGE_DISPLAYED + NUM_PAGES_OUTSIDE_RANGE + 1:
        in_leading_range = in_trailing_range = True
        page_range = [n for n in range(1, pages + 1)]
    elif page <= LEADING_PAGE_RANGE:
        in_leading_range = True
        page_range = [n for n in range(1, LEADING_PAGE_RANGE_DISPLAYED + 1)]
        pages_outside_leading_range = [n + pages for n in range(0, -NUM_PAGES_OUTSIDE_RANGE, -1)]
    elif page > pages - TRAILING_PAGE_RANGE:
        in_trailing_range = True
        page_range = [n for n in range(pages - TRAILING_PAGE_RANGE_DISPLAYED + 1, pages + 1) if n > 0 and n <= pages]
        pages_outside_trailing_range = [n + 1 for n in range(0, NUM_PAGES_OUTSIDE_RANGE)]
    else:
        page_range = [n for n in range(page - ADJACENT_PAGES, page + ADJACENT_PAGES + 1) if n > 0 and n <= pages]
        pages_outside_leading_range = [n + pages for n in range(0, -NUM_PAGES_OUTSIDE_RANGE, -1)]
        pages_outside_trailing_range = [n + 1 for n in range(0, NUM_PAGES_OUTSIDE_RANGE)]

    # Now try to retain GET params, except for 'page'
    # Add 'django.core.context_processors.request' to settings.TEMPLATE_CONTEXT_PROCESSORS beforehand
    request = context['request']
    params = request.GET.copy()
    if 'page' in params:
        del params['page']
    if 'partial' in params:
        del params['partial']
    get_params = params.urlencode()

    return {
        'pages': pages,
        'page': page,
        'previous': page_obj.previous_page_number() if page_obj.has_previous() else None,
        'next': page_obj.next_page_number() if page_obj.has_next() else None,
        'has_previous': page_obj.has_previous(),
        'has_next': page_obj.has_next(),
        'page_range': page_range,
        'in_leading_range': in_leading_range,
        'in_trailing_range': in_trailing_range,
        'pages_outside_leading_range': pages_outside_leading_range,
        'pages_outside_trailing_range': pages_outside_trailing_range,
        'get_params': get_params,
        'allow_single_page': context.get('allow_single_page')
    }
