{% load markup thumbnail %}
{% if page.has_previous or page.has_next %}<div class="focus">{% include "pagination.inc" %}</div>{% endif %}
{% for statement in page.object_list %}{% with statement.name_info as name_info %}
<div class="statement{% if forloop.first %} first{% endif %}{% if highlight_statement == statement.sequence %} highlighted{% endif %}" id="s{{ statement.sequence }}">
<div class="context clearafter"><p><strong>{{ statement.topic }}</strong><br>{{ statement.heading }}</p><p>{% if statements_full_date %}{{ statement.time|date:"F jS, Y / P" }}{% else %}{{ statement.time|date:"P"|capfirst }}{% endif %}{% if statements_context_link %}<br><a href="{{ statement.get_absolute_url }}">See context</a>{% endif %}</p>{% if statement.member %}{% if name_info.post %}<p>{{ statement.member.riding.dashed_name }}<br>{{ statement.member.riding.get_province_display }}</p>{% endif %}<p><span class="tag partytag_{{ statement.member.party.slug|lower }}">{{ statement.member.party.short_name }}</span></p>{% endif %}</div>

<div class="focus{% if not statement.politician.headshot %} nophoto{% endif %}">{% if statement.politician.headshot %}<img src="{% thumbnail statement.politician.headshot 67x90 crop_first="28,20,68,20" %}" class="headshot_thumb">{% endif %}<a name="s{{ statement.sequence }}"></a><p class="speaking">{% if statement.member %}<a href="{{ statement.member.politician.get_absolute_url }}">{% endif %}<span class="pol_name">{{ name_info.display_name }}</span>{% if statement.member %}</a> <span class="pol_affil">{% if name_info.post %}{{ name_info.post }}</span>{% else %}{# else post #}{% if not name_info.named %}{{ statement.member.politician.name }}{% else %}{# else named #}{{ statement.member.riding.dashed_name }}, {{ statement.member.riding.province }}{% endif %}{# end named #}{% endif %}{# end post #}</span>{% endif %}{# end member #}</p>
{{ statement.text_html }}</div>
<div class="clear"></div>
</div>
{% endwith %}{% endfor %}
<div class="focus">{% include "pagination.inc" %}</div>

{% block headextra %}
<script type="text/javascript">
$(function() {
    /* $('.statement .context').each(function() {
        // We want all of our divs to have heights that are multiples of 10.
        // This only breaks with smaller font sizes, which is what we have in .statement .context
        if (this.clientHeight % 10 != 0) {
            $(this).css('padding-bottom', (10 - (this.clientHeight % 10)) +'px');
        }
    }); */
    function revealStatement() {
        $(this).hide()
            .parent().children('.fadeout').hide()
            .parent().children('.truncated').animate({
                maxHeight: '800px'
            }, 'slow', 'linear',
            function () {
                $(this).addClass('displayall').css('max-height', 'none').removeClass('truncated');
        });
    }
    
    function addMoreLinks() {
        $('.statement .focus:not(.truncated)').each(function() {
           if (this.clientHeight < this.scrollHeight) {
               $(this).addClass('truncated');
               var $morelink = $(document.createElement('div')).addClass('morelink').click(revealStatement);
               var $fadeout = $(document.createElement('div')).addClass('fadeout');
               $(this).parent().append($morelink).append($fadeout);
           }
        });
    }
    addMoreLinks();
    
    $('.pagelink').live('click', function(e) {
        e.preventDefault();
        var $paginated = $('#paginated');
        $(this).parent().addClass('loading');
        $paginated.load(this.href, '', function() {
            addMoreLinks();
            if ($(document).scrollTop() > $paginated.offset().top) { 
                $('html,body').animate({scrollTop: $('#paginated').offset().top - 15});
            }
        });
    });
    
    {% if highlight_statement %}$('html, body').animate({scrollTop: $('#s{{ highlight_statement }}').offset().top - 15});{% endif %}
});
</script>
{% endblock headextra %}