<div class="focus">
<h2>{% if page.paginator.count == 1%}The lone result{% else %}Results {{ page.start_index }}-{{ page.end_index }} of {{ page.paginator.count }}{% endif %}</h2>
</div>
<div class="focus">{% include "pagination.inc" %}</div>
    {% for result in page.object_list %}<div class="result statement" data-url="{{ result.url }}">
    {% if result.django_ct == 'core.politician' %}<div class="context"><p><strong>Politician</strong></p></div>
        <div class="focus"><p><a href="{{ result.url }}" class="pol_name">{{ result.politician }}</a> {{ result.text }}</p></div>{% endif %}
    {% if result.django_ct == 'hansards.statement' %}
        <div class="context">
			<p>{{ result.date|date:"F jS, Y"}}
			<br>{% if result.committee %}{{ result.committee }} committee{% else %}House debate{% endif %}</p>
			<p>{% if result.politician_id %}<a href="/politicians/{{ result.politician_id }}/" class="pol_name">{{ result.politician }}</a>{% else %}{{ result.politician }}{% endif %}{% if result.party %}<br><span class="tag partytag_{{ result.party|slugify }}">{{ result.party }}</span>{% endif %}</p></div>
        <div class="focus"><p><a href="{{ result.url }}#hl" class="statement_topic">{% if result.topic %}{{ result.topic }}{% else %}(no topic){% endif %}</a> &nbsp;{{ result.text }}</p></div>
        <div class="clear"></div>
    {% endif %}
    {% if result.django_ct == 'bills.bill' %}<div class="context"><p><strong>Legislation</strong></p></div>
        <div class="focus"><p><a href="{{ result.url }}">Bill {{ result.number }}</a> <span class="pol_affil">({{ result.session}})</span></p><p>{{ result.text }}</p></div>{% endif %}</div>
    {% endfor %}
    <div class="focus">{% include "pagination.inc" %}</div>