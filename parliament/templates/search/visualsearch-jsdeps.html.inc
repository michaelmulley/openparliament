{% load compress %}
{% compress js %}
<script type="text/javascript" src="{{ STATIC_URL }}js/libs/jquery.ui.core.js"></script>
<script type="text/javascript" src="{{ STATIC_URL }}js/libs/jquery.ui.position.js"></script>
<script type="text/javascript" src="{{ STATIC_URL }}js/libs/jquery.ui.widget.js"></script>
<script type="text/javascript" src="{{ STATIC_URL }}js/libs/jquery.ui.autocomplete.js"></script>
<script type="text/javascript" src="{{ STATIC_URL }}js/libs/underscore.js"></script>
<script type="text/javascript" src="{{ STATIC_URL }}js/libs/backbone.js"></script>

<script type="text/javascript" src="{{ STATIC_URL }}js/libs/visualsearch.js"></script>
<script type="text/javascript" src="{{ STATIC_URL }}js/searchdata.js"></script>
{% endcompress %}