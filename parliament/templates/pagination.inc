{% if page.has_previous or page.has_next %}<div class="pagination">
        {% if page.has_previous %}
            <a href="?page={{ page.previous_page_number }}" class="pagelink prev"></a>
        {% endif %}

        <span>
            Page {{ page.number }} of {{ page.paginator.num_pages }}
        </span>

        {% if page.has_next %}
            <a href="?page={{ page.next_page_number }}" class="pagelink next"></a>
        {% endif %}
</div>{% endif %}