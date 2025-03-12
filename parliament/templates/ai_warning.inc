{% load static %}
<img class="ai_warning_icon" src="{% static "images/robot-1.svg" %}" alt="line drawing of robot">
<p class="ai_warning_text"><span {% if hl %}class="hl"{% endif %}>{% if summary_of %}This is a <b>computer-generated</b> summary of {{ summary_of }}.{% else %}This summary is <b>computer-generated</b>.{% endif %}
Usually it&rsquo;s accurate, but every now and then it&rsquo;ll contain inaccuracies or total fabrications.</span></p>