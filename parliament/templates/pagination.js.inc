<script type="text/javascript" src="{{ MEDIA_URL }}js/jquery.bbq.js"></script>
<script type="text/javascript">
$(function() {
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
    if ($('.statement_browser').length) {
        addMoreLinks();
    }
    var $paginated = $('#paginated');
    $('.pagelink').live('click', function(e) {
        e.preventDefault();
        var $pagelink = $(this);
        $.bbq.pushState($.deparam.querystring(this.href));
        showPaginated = $pagelink.hasClass('show_paginated_div');
        if (showPaginated) {
            $(this).html('Loading...')
        }
        $paginated.find('.pagination').addClass('loading');
    });
    
    $(window).bind('hashchange', function(e) {
        if (e.fragment && e.fragment != 'hl') {
            $paginated.find('.pagination').addClass('loading');
            $paginated.load('?' + e.fragment, '', function() {
                var scrollDown = Boolean($(document).scrollTop() > $paginated.offset().top);
                if ($paginated.is(':hidden')) {
                    $('.show_paginated_div').hide()
                    $('#paginated_wrapper').show();
                    scrollDown = true;
                }
                if ($('.statement_browser').length) {
                    addMoreLinks();
                }
                $('.related_link').tooltip({delay: 200, showURL: false});
                if (scrollDown) { 
                    $('html,body').animate({scrollTop: $paginated.offset().top - 15});
                }
                showPaginated = false;
            });
        }
    });
    
    if (location.hash) {
        $(window).trigger('hashchange');
    }
    
    {% if highlight_statement %}$('html, body').animate({scrollTop: $('#hl').offset().top - 15});{% endif %}
});
</script>