{% load ours %}{% with document.get_absolute_url as docurl %}
<div id="hansard-topics">
{% for section in topics_data %}
<p><a href="{{ docurl }}{{ section.slug}}/">{{ section.display_heading }}</a>
{% comment %} {% if section.subheds %}
    about
    {% for subhed in section.subheds %}<a href="{{ docurl }}{{ subhed.1 }}/">{{ subhed.0 }}</a>{% if not forloop.last %}<span style="padding:0 0.6rem">❖</span>{% endif %}{% endfor %}
{% endif %} {% endcomment %}
{% if section.bill_debated %}
    {% if section.bill_debate_stage == '1' %}First reading of{% endif %}{% if section.bill_debate_stage == '2' %}Second reading of{% endif %}{% if section.bill_debate_stage == '3' %}Third reading of{% endif %}{% if section.bill_debate_stage == 'report' %}Report stage of{% endif %}
    <a href="{% url "bill" session_id=document.session_id bill_number=section.bill_debated %}">Bill {{section.bill_debated}}</a>.
{% endif %}
{% if section.summary_text %} {{ section.summary_text|markdown_links }}{% endif %}
{% if not section.summary_chunks and not section.subheds %}
    <em>{% if section.wordcount > 100 %}{{ section.wordcount|round:-2 }} words{% endif %}{% if section.minutes > 5 %}, {{ section.minutes|friendly_minutes }}{% endif %}{% if section.other_segments %} in {{ section.other_segments|length|add:1 }} segments: <a href="{{ docurl }}{{ section.slug }}/">1</a> {% for slug in section.other_segments %} <a href="{{ docurl }}{{ slug }}/">{{ forloop.counter|add:1 }}</a>{% endfor %}{% endif %}.
    </em>
{% endif %}
</p>
{% if section.summary_chunks %}
<div class="row tile small-up-1 large-up-2 hansard-topics-subsection">
    {% for chunk in section.summary_chunks %}
        <div class="column column-block">
            {{ chunk|markdown_links }}
        </div>
    {% endfor %}
</div>

{% endif %}
{% if section.subheds %}
<div class="row tile dense small-up-1 medium-up-2 hansard-topics-subsection">
    {% for subhed in section.subheds %}
        <div class="column column-block oneline overflowtip">
            <a href="{{ docurl }}{{ subhed.1 }}/">{{ subhed.0 }}</a>
        </div>
    {% endfor %}
</div>
{% endif %}
{% endfor %}
</div>
{% endwith %}