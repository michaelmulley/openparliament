<div class="row tile dense small-up-2 medium-up-4">{% for meeting in meetings %}
	<div class="column column-block{% if not meeting.evidence_id %} no_evidence{% endif %}">
		<a href="{% url "committee_meeting" committee_slug=committee.slug session_id=meeting.session_id number=meeting.number %}">{{ meeting.date|date:"N j" }}{% if include_year %}, {{ meeting.date|date:"Y" }}{% endif %}</a>
		{% if meeting.in_camera %} <i class="icon-lock tip" title="This meeting was held in camera. That means we don't get to know what happened."></i>{% endif %}
	</div>{% endfor %}
</div>
