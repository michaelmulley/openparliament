{% load static %}
{% if reading_summary %}
<div class="row statement ai_summary first">
  <div class="context-col">
    <h2>Debate Summary</h2>
  </div>
  <div class="text-col" data-id="summary-{{ reading_summary.id }}">
    {% include "ai_warning.inc" with summary_of="the speeches below" hl=1 %}
    {{ reading_summary.get_html }}
    {% include "summary_poll.inc" with summary=reading_summary hl=1 %}
  </div>
</div>
{% endif %}


{% include "hansards/statement_page.inc" %}