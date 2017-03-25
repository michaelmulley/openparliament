{% load json pagination %}
{% if page %}
<div class="row search_header" data-years="{{ chart_years|join:"," }}" data-values="{{ chart_values|join:"," }}" data-sort="{{ sort }}" data-discontinuity="{{ discontinuity }}">
		<div class="columns small-12 medium-4 result_summary">{% if page.paginator.count == 0%}<h2>No results found</h2>{% elif page.paginator.count == 1 %}{# The lone result #}{% else %}Results <strong>{{ page.start_index }}</strong>-<strong>{{ page.end_index }}</strong> of <strong>{{ page.paginator.count }}</strong>{% endif %}</div>
		{% if page.paginator.count > 5 %}
			<div class="columns small-12 medium-8 sort_options">{% if 'date' in sort %}<a href="?q={{ query|urlencode }}" data-sort="">Sort by relevance</a>{% else %}Sorted by relevance{% endif %} | {% if 'date' in sort %}Sorted{% else %}Sort{% endif %} by date: {% if 'desc' in sort %}newest first{% else %}<a href="?q={{ query|urlencode }}&amp;sort=date+desc" data-sort="date desc">newest first</a>{% endif %} / {% if 'asc' in sort %}oldest first{% else %}<a href="?q={{ query|urlencode }}&amp;sort=date+asc" data-sort="date asc">oldest first</a>{% endif %}</div>
		{% endif %}
</div>
{% for result in page.object_list %}
<div class="row result" data-url="{{ result.url }}">

{% if result.django_ct == 'core.politician' %}
    <div class="search-main-col">
    	<p><a href="{{ result.url }}" class="pol_name">{{ result.politician }}</a> {{ result.text }}</p>
    </div>
    {#		<div class="search-context-col"><p><strong>Politician</strong></p></div>#}
{% endif %}

{% if result.django_ct == 'hansards.statement' %}
    <div class="search-main-col">
    	<p><a href="{{ result.url }}#hl" class="statement_topic">{% if result.topic %}{{ result.topic }}{% elif result.committee %}{{ result.committee }} committee{% else %}House debate{% endif %}</a> &nbsp;{{ result.text }}</p>
    </div>
    <div class="search-context-col">
		<p>{{ result.date|date:"F jS, Y"}}<span class="br slash"></span>{% if result.committee %}Committee meeting{% else %}House debate{% endif %}</p>
		<p>{% if result.politician_id %}<a href="/politicians/{{ result.politician_id }}/" class="pol_name">{{ result.politician }}</a>{% else %}<strong>{{ result.politician }}</strong>{% endif %}{% if result.party %}<span class="br space"></span><span class="tag partytag_{{ result.party|slugify }}">{{ result.party }}</span>{% endif %}</p>
	</div>    
{% endif %}

{% if result.django_ct == 'bills.bill' %}
	<div class="search-main-col">
		<p><a href="{{ result.url }}">Bill {{ result.number }}</a> <span class="pol_affil">{{ result.title }}</span></p><p>{{ result.text }}</p>
	</div>
	<div class="search-context-col">
		<p>{{ result.date|date:"F jS, Y"}}<br>Bill</p>
		<p>{% if result.politician_id %}<a href="/politicians/{{ result.politician_id }}/" class="pol_name">{{ result.politician }}</a>{% if result.party %}<span class="br space"></span><span class="tag partytag_{{ result.party|slugify }}">{{ result.party }}</span>{% endif %}{% endif %}</p>
	</div>
{% endif %}

</div>
{% endfor %}

{% foundation_paginator as pagination %}{{ pagination }}

{% endif %}{# endif page #}
<script type="text/javascript">
	$(document).one('contentLoad', function() {
		var facetData = [
			{
				filterName: 'Party',
				pluralName: 'Parties',
				rawValues: {{ facet_fields.party|json }}
			},
			{
				filterName: 'Province',
				pluralName: 'Provinces',
				rawValues: {{ facet_fields.province|json }},
				labelFunc: function(v) { return OP.PROVINCES[v]; }
			},
			{
				filterName: 'Person',
				pluralName: 'People',
				rawValues: {{ facet_fields.politician|json }}
			},
			{
				filterName: 'Type',
				pluralName: 'Result Type',
				rawValues: {{ facet_fields.doctype|json }},
				labelFunc: function(v) { return OP.search.DOCTYPES[v]; }
			}
		];
		$(document).trigger('op_search_results_loaded', {
			facets: facetData,
			resultCount: {{ page.paginator.count|json }}
		});
	});
</script>
