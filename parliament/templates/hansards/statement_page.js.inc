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