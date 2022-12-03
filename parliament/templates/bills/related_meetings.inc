<div class="row"><div class="context-col"></div><div class="main-col">
	{% for m in committee_meetings %}
	<p><a href="{{ m.get_absolute_url }}">{{ m.committee.title }}, on {{ m.date }}</a></p>

	{% if m.evidence %}<ul class="tile meeting-attendees">{% for speaker_name, speaker_info in m.evidence.outside_speaker_summary.items %}
		<li class="five threeline quiet overflowtip"><a href="{{ m.evidence.get_absolute_url }}{{ speaker_info.slug }}/">{{ speaker_name }}</a>{% if speaker_info.description %}, {{ speaker_info.description }}{% endif %}</li>{% endfor %}</ul><div class="clear spacer"></div>{% endif %}
	
	{% endfor %}
</div></div>