{% load i18n %}
{% if page.has_previous or page.has_next %}<div class="pagination">
        {% if page.has_previous %}
            <a href="{{ pagination_url }}?page={{ page.previous_page_number }}{% if page.querystring %}&amp;{{ page.querystring }}{% endif %}" class="pagelink prev"></a>
        {% endif %}

        <span>{% blocktrans with page.number as page_number and page.paginator.num_pages as page_paginator_num_pages %}
            Page {{ page_number }} of {{ page_paginator_num_pages }}
        {% endblocktrans %}</span>

        {% if page.has_next %}
            <a href="{{ pagination_url }}?page={{ page.next_page_number }}{% if page.querystring %}&amp;{{ page.querystring }}{% endif %}" class="pagelink next"></a>
        {% endif %}
</div>{% endif %}