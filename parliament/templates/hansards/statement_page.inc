{% load markup thumbnail %}
{% if highlight_statement or highlight_statement == 0 %}
	<script type="text/javascript">
		$(function () {
			$('html, body').animate({scrollTop:$('#hl').offset().top - 15});
		});
	</script>
{% endif %}
{% if page.has_previous or page.has_next %}
	<div class="focus">{% include "pagination.inc" %}</div>
{% endif %}
{% for statement in page.object_list %}{% with statement.name_info as name_info %}
	{% with statement.get_absolute_url as statementurl %}
		<div class="statement{% if forloop.first %} first{% endif %}{% if highlight_statement == statement %} highlighted{% endif %}"
			 {% if highlight_statement == statement %}id="hl"{% else %}id="s{{ statement.sequence }}"{% endif %}
			 data-url="{{ statementurl }}">
			<div class="context clearafter">
				<noscript><p><a href="{{ statementurl }}only/">Permalink</a></p></noscript>
				{% if statement.who %}
					{% if statement.h2 %}
						<p><strong class="statement_topic">{% if statement.h3 %}{{ statement.h3 }}</strong><br>{{ statement.h2 }}{% else %}{{ statement.h2 }}</strong>{% endif %}<br>{{ statement.h1 }}</p>
					{% endif %}{# endif h1 #}
					<p>{% if statements_full_date or highlight_statement == statement %}{{ statement.time|date:"F jS, Y / P" }}{% else %}{% if hansard %}{% if hansard.date.day != statement.time.day %}<strong>{{ statement.time|date:"F jS" }}</strong>, {% endif %}{% endif %}{# double endif for hansard.date #}{{ statement.time|date:"P"|capfirst }}{% endif %}{# endif full_date #}
				{% endif %}{# endif statement.who #}
				{% if statements_context_link %}<br><a href="{{ statementurl }}">See
					context</a>{% endif %}{# endif context_link #}

				{% if statement.member %}{% if name_info.post %}<p>{{ statement.member.riding.dashed_name }}
				<br>{{ statement.member.riding.get_province_display }}</p>{% endif %}{# endif post #}<p><span
						class="tag partytag_{{ statement.member.party.slug|lower }}">{{ statement.member.party.short_name }}</span>
				</p>{% endif %}{# endif member #}{% if name_info.post_reminder %}
					<p>{{ name_info.post_reminder }}</p>{% endif %}</div>

			<div class="focus{% if not statement.member.politician.headshot %} nophoto{% endif %}{% if not statement.who %} nospeaker{% endif %}">
				<div>{% if statement.member.politician.headshot %}<a
						href="{{ statement.member.politician.get_absolute_url }}"><img
						src="{% thumbnail statement.member.politician.headshot 67x90 crop_first="28,20,68,20" %}"
						class="headshot_thumb" alt=""></a>{% endif %}{% if statement.who %}<p class="speaking">
					{% if statement.member %}<a href="{{ statement.member.politician.get_absolute_url }}">{% endif %}
					<span class="pol_name">{{ name_info.display_name }}</span>
					{% if statement.member or name_info.post %}{% if statement.member %}</a>{% endif %} <span
							class="pol_affil">{% if name_info.post %}{{ name_info.post }}{% else %}{# else post #}
						{% if not name_info.named %}{{ statement.member.politician.name }}{% else %}{# else named #}{{ statement.member.riding.dashed_name }}, {{ statement.member.riding.province }}{% endif %}{# end named #}{% endif %}{# end post #}</span>{% endif %}{# end member #}
					</p>{% endif %}{# endif != Proceedings #}
					{{ statement.text_html }}</div>
			</div>
			<div class="clear"></div>
		</div>
	{% endwith %}{% endwith %}{% endfor %}
<div class="focus statement_browser">{% include "pagination.inc" %}</div>
