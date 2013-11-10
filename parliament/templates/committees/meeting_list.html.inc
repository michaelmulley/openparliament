<ul class="tile">{% for meeting in meetings %}
	<li class="three online overflowtip{% if not meeting.evidence_id %} no_evidence{% endif %}">
		<a href="{% url committee_meeting committee_slug=committee.slug session_id=meeting.session_id number=meeting.number %}">{{ meeting.date|date:"N j" }}{% if include_year %}, {{ meeting.date|date:"Y" }}{% endif %}</a>
		{% if meeting.in_camera %} <i class="icon-lock tip" title="This meeting was held in camera. That means we don't get to know what happened."></i>{% endif %}
	</li>{% endfor %}
</ul>
<div class="clear"></div>