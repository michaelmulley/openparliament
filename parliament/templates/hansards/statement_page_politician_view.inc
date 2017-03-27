{% load pagination %}
{% foundation_paginator as pagination %}
{{ pagination }}
{% for statement in page.object_list %}
<div class="row statement_browser statement" data-url="{{ statement.get_absolute_url }}" data-floor="{{ statement.content_floor_if_necessary }}" {% if statement.source_id and statement.source_id.isdigit %}data-hocid="{{ statement.source_id }}"{% endif %}>
	<div class="text-col {% if forloop.first %} first{% endif %}" id="s{{ statement.sequence }}">
		<p class="speaking"><a href="{{ statement.get_absolute_url }}#hl" class="statement_topic">{{ statement.topic }}</a> <span class="pol_affil">{{ statement.time|date:"F jS, Y" }}</span></p>
		<div class="text">{{ statement.text_html }}</div>
	</div>
	<div class="r-ctx-col">
		<div class="sharing-tools"><span>Links &amp; Sharing</span></div>
		<div class="lang-control"><span></span></div>
		<div class="lang-preference-switch" style="display:none"><span></span></div>
	</div>
</div>
{% endfor %}
{{ pagination }}
{% include "hansards/sharing_tools.inc" %}