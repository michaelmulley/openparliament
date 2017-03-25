{% load static compress %}

{% compress js %}
<script type="text/javascript" src="{% static 'jsnew/vendor/jquery-ui.js' %}"></script>

<script type="text/javascript" src="{% static 'bower_components/backbone/backbone.js' %}"></script>

<script type="text/javascript" src="{% static 'jsnew/vendor/visualsearch.js' %}"></script>

<script type="text/javascript" src="{% static 'js/search/search.js' %}"></script>
<script type="text/javascript" src="{% static 'js/search/searchdata.js' %}"></script>
<script type="text/javascript" src="{% static 'js/search/datefilter.js' %}"></script>
<script type="text/javascript" src="{% static 'js/search/facets.js' %}"></script>

{% endcompress %}