{% if page.has_previous or page.has_next %}<div class="pagination">
        {% if page.has_previous %}
            <a href="{{ pagination_url }}?page={{ page.previous_page_number }}{% if page.querystring %}&amp;{{ page.querystring }}{% endif %}" class="pagelink prev"></a>
        {% endif %}

        <span>
            {% if pagination_show_result_counts %}
				Results {{ page.start_index }}&#8211;{{ page.end_index }} of {{ page.hits }}
			{% else %}
				Page {{ page.number }} of {{ page.paginator.num_pages }}
			{% endif %}
        </span>

        {% if page.has_next %}
            <a href="{{ pagination_url }}?page={{ page.next_page_number }}{% if page.querystring %}&amp;{{ page.querystring }}{% endif %}" class="pagelink next"></a>
        {% endif %}
</div>{% endif %}