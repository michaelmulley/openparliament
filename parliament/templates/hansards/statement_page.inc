{% load pagination %}
{% if highlight_statement or highlight_statement == 0 %}
	<script type="text/javascript">
		$(function () {
			if (!window.location.hash) {
				setTimeout(
					function() { $('html, body').animate({scrollTop:$('#hl').offset().top - 15}); },
					5
				);
			}
		});
	</script>
{% endif %}
{% foundation_paginator as pagination %}
{{ pagination }}
{% for statement in page.object_list %}{% with statement.name_info as name_info %}
	{% with statement.get_absolute_url as statementurl %}
		<div class="row statement_browser statement{% if forloop.first %} first{% endif %}{% if highlight_statement == statement %} highlighted{% endif %}"
			 {% if highlight_statement == statement %}id="hl"{% else %}id="s{{ statement.slug }}"{% endif %}
			 data-url="{{ statementurl }}" data-floor="{{ statement.content_floor_if_necessary }}" {% if statement.source_id and statement.source_id.isdigit %}data-hocid="{{ statement.source_id }}"{% endif %}>
			<div class="l-ctx-col">
				<noscript><p><a href="{{ statementurl }}only/">Permalink</a></p></noscript>
				{% if statement.who %}
					{% if statement.h2 %}
						<p>
						{% if document and not bill and statement.bill_debated %}<a href="{% url "bill" session_id=document.session.id bill_number=statement.bill_debated.number %}">Bill {{ statement.bill_debated.number }}</a><span class="br"></span>{% endif %}
						<strong class="statement_topic">{% if statement.h3 %}{{ statement.h3 }}</strong><span class="br"></span>{{ statement.h2 }}{% else %}{{ statement.h2 }}</strong>{% endif %}<span class="br"></span>{{ statement.h1 }}</p>
					{% endif %}{# endif h1 #}
					<p><a class="statement_time_permalink" href="{{ statementurl }}only/">{% if statements_full_date or highlight_statement == statement %}{{ statement.time|date:"F jS, Y / P" }}{% else %}{% if hansard %}{% if hansard.date.day != statement.time.day %}<strong>{{ statement.time|date:"F jS" }}</strong>, {% endif %}{% endif %}{# double endif for hansard.date #}{{ statement.time|date:"P"|capfirst }}{% endif %}{# endif full_date #}</a></p>
				{% endif %}{# endif statement.who #}
				{% if statements_context_link %}<br><a href="{{ statementurl }}">See
					context</a>{% endif %}{# endif context_link #}

				{% if statement.member %}{% if name_info.post %}<p>{{ statement.member.riding.dashed_name }}
				<span class="br"></span>{{ statement.member.riding.get_province_display }}</p>{% endif %}{# endif post #}
				{% if not name_info.speaker %}<p class="partytag"><span
						class="tag partytag_{{ statement.member.party.slug|lower }}">{{ statement.member.party.short_name }}</span>
				</p>{% endif %}{% endif %}{# endif member #}{% if name_info.post_reminder %}
					<p>{{ name_info.post_reminder }}</p>{% endif %}</div>

			<div class="text-col {% if not statement.member.politician.headshot %} nophoto{% endif %}{% if not statement.who %} nospeaker{% endif %}">
				{% if statement.member.politician.headshot_thumbnail %}
					<a href="{{ statement.member.politician.get_absolute_url }}">
					<img src="{{ statement.member.politician.headshot_thumbnail.url }}" class="headshot_thumb">
					</a>
				{% endif %}
				{% if statement.who %}<p class="speaking">
					{% if name_info.url %}<a href="{{ name_info.url }}">{% endif %}
					<span class="pol_name">{{ name_info.display_name }}</span>
					{% if name_info.url %}</a>{% endif %}{% if statement.member or name_info.post %} {% if statement.member and not name_info.speaker %}<span
						class="partytag tag partytag_{{ statement.member.party.slug|lower }}">{{ statement.member.party.short_name }}</span>{% endif %}<span
							class="pol_affil">{% if name_info.post %}{{ name_info.post }}{% else %}{# else post #}
						{% if not name_info.named %}{{ statement.member.politician.name }}{% else %}{# else named #}{{ statement.member.riding.dashed_name }}, {{ statement.member.riding.province }}{% endif %}{# end named #}{% endif %}{# end post #}</span>{% endif %}{# end member #}
					</p>{% endif %}{# endif != Proceedings #}
					<div class="text">{{ statement.text_html }}</div>
			</div>
	
			<div class="r-ctx-col">
				<div class="sharing-tools"><span>Links &amp; Sharing</span></div>
				<div class="lang-control"><span></span></div>
				<div class="lang-preference-switch" style="display:none"><span></span></div>
			</div>
		</div>
	{% endwith %}{% endwith %}{% endfor %}
{{ pagination }}
{% include "hansards/sharing_tools.inc" %}
