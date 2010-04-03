{% load markup thumbnail %}
{% if page.has_previous or page.has_next %}<div class="focus">{% include "pagination.inc" %}</div>{% endif %}
{% for statement in page.object_list %}{% with statement.name_info as name_info %}
<div class="statement{% if forloop.first %} first{% endif %}{% if highlight_statement == statement.sequence %} highlighted{% endif %}" id="s{{ statement.sequence }}">
<div class="context clearafter"><p><strong>{{ statement.topic }}</strong><br>{{ statement.heading }}</p><p>{% if statements_full_date %}{{ statement.time|date:"F jS, Y / P" }}{% else %}{{ statement.time|date:"P"|capfirst }}{% endif %}{% if statements_context_link %}<br><a href="{{ statement.get_absolute_url }}">See context</a>{% endif %}</p>{% if statement.member %}{% if name_info.post %}<p>{{ statement.member.riding.dashed_name }}<br>{{ statement.member.riding.get_province_display }}</p>{% endif %}<p><span class="tag partytag_{{ statement.member.party.slug|lower }}">{{ statement.member.party.short_name }}</span></p>{% endif %}</div>

<div class="focus{% if not statement.member.politician.headshot %} nophoto{% endif %}">{% if statement.member.politician.headshot %}<img src="{% thumbnail statement.member.politician.headshot 67x90 crop_first="28,20,68,20" %}" class="headshot_thumb">{% endif %}<a name="s{{ statement.sequence }}"></a><p class="speaking">{% if statement.member %}<a href="{{ statement.member.politician.get_absolute_url }}">{% endif %}<span class="pol_name">{{ name_info.display_name }}</span>{% if statement.member %}</a> <span class="pol_affil">{% if name_info.post %}{{ name_info.post }}</span>{% else %}{# else post #}{% if not name_info.named %}{{ statement.member.politician.name }}{% else %}{# else named #}{{ statement.member.riding.dashed_name }}, {{ statement.member.riding.province }}{% endif %}{# end named #}{% endif %}{# end post #}</span>{% endif %}{# end member #}</p>
{{ statement.text_html }}</div>
<div class="clear"></div>
</div>
{% endwith %}{% endfor %}
<div class="focus">{% include "pagination.inc" %}</div>
