{% if page %}
	<div class="focus">
	<div class="search_header" data-years="{{ chart_years|join:"," }}" data-values="{{ chart_values|join:"," }}">
		{% if page.paginator.count > 5 %}<div class="sort_options" style="float: right">{% if 'date' in sort %}<a href="?q={{ query|urlencode }}">Sort by relevance</a>{% else %}Sorted by relevance{% endif %} | {% if 'date' in sort %}Sorted{% else %}Sort{% endif %} by date: {% if 'desc' in sort %}newest first{% else %}<a href="?q={{ query|urlencode }}&amp;sort=date+desc">newest first</a>{% endif %} / {% if 'asc' in sort %}oldest first{% else %}<a href="?q={{ query|urlencode }}&amp;sort=date+asc">oldest first</a>{% endif %}</div>{% endif %}
		<div class="result_summary" style="float: left">{% if page.paginator.count == 0%}<h2>No results found</h2>{% elif page.paginator.count == 1 %}The lone result{% else %}Results <strong>{{ page.start_index }}</strong>-<strong>{{ page.end_index }}</strong> of <strong>{{ page.paginator.count }}</strong>{% endif %}</div>
	</div>
	</div>
    {% for result in page.object_list %}<div class="result statement" data-url="{{ result.url }}">
    {% if result.django_ct == 'core.politician' %}<div class="context"><p><strong>Politician</strong></p></div>
        <div class="focus"><p><a href="{{ result.url }}" class="pol_name">{{ result.politician }}</a> {{ result.text }}</p></div>{% endif %}
    {% if result.django_ct == 'hansards.statement' %}
        <div class="context">
			<p>{{ result.date|date:"F jS, Y"}}
			<br>{% if result.committee %}Committee meeting{% else %}House debate{% endif %}</p>
			<p>{% if result.politician_id %}<a href="/politicians/{{ result.politician_id }}/" class="pol_name">{{ result.politician }}</a>{% else %}<strong>{{ result.politician }}</strong>{% endif %}{% if result.party %}<br><span class="tag partytag_{{ result.party|slugify }}">{{ result.party }}</span>{% endif %}</p></div>
        <div class="focus"><p><a href="{{ result.url }}#hl" class="statement_topic">{% if result.topic %}{{ result.topic }}{% elif result.committee %}{{ result.committee }} committee{% else %}(no topic){% endif %}</a> &nbsp;{{ result.text }}</p></div>
        <div class="clear"></div>
    {% endif %}
    {% if result.django_ct == 'bills.bill' %}<div class="context"><p><strong>Legislation</strong></p></div>
        <div class="focus"><p><a href="{{ result.url }}">Bill {{ result.number }}</a> <span class="pol_affil">({{ result.session}})</span></p><p>{{ result.text }}</p></div>{% endif %}</div>
    {% endfor %}
    <div class="focus">{% include "pagination.inc" %}</div>
{% endif %}{# endif page #}
<script type="text/javascript">
	$(function() {
		$(document).trigger('op_search_results_loaded');
	});
</script>
