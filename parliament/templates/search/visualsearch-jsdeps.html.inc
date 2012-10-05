{% load compress %}

<!--[if lte IE 8]>
<script type="text/javascript" src="{{ STATIC_URL }}js/libs/excanvas.min.js"></script>
<![endif]-->

{% compress js %}
<script type="text/javascript" src="{{ STATIC_URL }}js/libs/jquery.ui.core.js"></script>
<script type="text/javascript" src="{{ STATIC_URL }}js/libs/jquery.ui.position.js"></script>
<script type="text/javascript" src="{{ STATIC_URL }}js/libs/jquery.ui.widget.js"></script>
<script type="text/javascript" src="{{ STATIC_URL }}js/libs/jquery.ui.mouse.js"></script>
<script type="text/javascript" src="{{ STATIC_URL }}js/libs/jquery.ui.autocomplete.js"></script>
<script type="text/javascript" src="{{ STATIC_URL }}js/libs/jquery.ui.slider.js"></script>

<script type="text/javascript" src="{{ STATIC_URL }}js/libs/backbone.js"></script>

<script type="text/javascript" src="{{ STATIC_URL }}js/libs/visualsearch.js"></script>

<script type="text/javascript" src="{{ STATIC_URL }}js/search.js"></script>
<script type="text/javascript" src="{{ STATIC_URL }}js/searchdata.js"></script>
<script type="text/javascript" src="{{ STATIC_URL }}js/datefilter.js"></script>
<script type="text/javascript" src="{{ STATIC_URL }}js/facets.js"></script>
{% endcompress %}