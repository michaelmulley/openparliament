{% load static compress %}

{% compress js %}
<script type="text/javascript" src="{% static 'bower_components/jquery-ui/ui/version.js' %}"></script>
<script type="text/javascript" src="{% static 'bower_components/jquery-ui/ui/widget.js' %}"></script>
<script type="text/javascript" src="{% static 'bower_components/jquery-ui/ui/position.js' %}"></script>
<script type="text/javascript" src="{% static 'bower_components/jquery-ui/ui/keycode.js' %}"></script>
<script type="text/javascript" src="{% static 'bower_components/jquery-ui/ui/unique-id.js' %}"></script>
<script type="text/javascript" src="{% static 'bower_components/jquery-ui/ui/safe-active-element.js' %}"></script>
<script type="text/javascript" src="{% static 'bower_components/jquery-ui/ui/widgets/autocomplete.js' %}"></script>
<script type="text/javascript" src="{% static 'bower_components/jquery-ui/ui/widgets/menu.js' %}"></script>
<script type="text/javascript" src="{% static 'bower_components/jquery-ui/ui/widgets/mouse.js' %}"></script>
<script type="text/javascript" src="{% static 'bower_components/jquery-ui/ui/widgets/slider.js' %}"></script>

<script type="text/javascript" src="{% static 'bower_components/backbone/backbone.js' %}"></script>

<script type="text/javascript" src="{% static 'js/vendor/visualsearch.js' %}"></script>

<script type="text/javascript" src="{% static 'js/search/search.js' %}"></script>
<script type="text/javascript" src="{% static 'js/search/searchdata.js' %}"></script>
<script type="text/javascript" src="{% static 'js/search/datefilter.js' %}"></script>
<script type="text/javascript" src="{% static 'js/search/facets.js' %}"></script>

{% endcompress %}