<ul class="tile">{% for meeting in meetings %}
	<li class="three online overflowtip{% if not meeting.evidence_id %} no_evidence{% endif %}">
		<a href="{% url committee_meeting committee_slug=committee.slug,session_id=meeting.session_id,number=meeting.number %}">{{ meeting.date|date:"N j" }}</a>
	</li>{% endfor %}
</ul>
<div class="clear"></div>