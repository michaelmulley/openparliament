<div class="focus">
<h2>{% if page.paginator.count == 1%}The lone result{% else %}Results {{ page.start_index }}-{{ page.end_index }} of {{ page.paginator.count }}{% endif %} for &ldquo;{{ query }}&rdquo;</h2>
</div>
<div class="focus">{% include "pagination.inc" %}</div>
    {% for result in page.object_list %}
    {% if result.django_ct == 'core.politician' %}<div class="result statement"><div class="context"><p><strong>Politician</strong></p></div>
        <div class="focus"><p><a href="{{ result.url }}">{{ result.pol_name }}</a> {{ result.text }}</p></div></div>{% endif %}
    {% if result.django_ct == 'hansards.statement' %}<div class="result statement">
        <div class="context"><p>{{ result.date|date:"F jS, Y"}}</p><p>{% if result.politician_id %}<a href="{% url politicians.views.politician pol_id=result.politician_id %}">{{ result.politician }}</a>{% else %}{{ result.politician }}{% endif %}{% if result.party %}<br><span class="tag partytag_{{ result.party|slugify }}">{{ result.party }}</span>{% endif %}</p></div>
        <div class="focus"><p><a href="{{ result.url }}">{% if result.topic %}{{ result.topic }}{% else %}(no topic){% endif %}</a> &nbsp;{{ result.text }}</p></div>
        <div class="clear"></div>
        </div>
    {% endif %}
    {% if result.django_ct == 'bills.bill' %}<div class="result bill"><div class="context"><p><strong>Legislation</strong></p></div>
        <div class="focus"><a href="{{ result.object.get_absolute_url }}">Bill {{ result.object.number }}</a> <span class="date">({{ result.object.session }})</span><p>{{ result.text }}</p></div></div>{% endif %}
    {% endfor %}
    <div class="focus">{% include "pagination.inc" %}</div>