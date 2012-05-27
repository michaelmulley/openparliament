$(function() {

    $('.pagelink').live('click', function(e) {
        e.preventDefault();
        History.pushState(null, null, this.href);
        if ($(this).hasClass('show_paginated_div')) {
            $(this).html('Loading...');
        }
        $('#paginated').find('.pagination').addClass('loading');
    });

    $(window).bind('statechange', function(e) {
        var newStateURL = History.getState().url;
        var $paginated = $('#paginated');
        $paginated.find('.pagination').addClass('loading');
        $paginated.load(newStateURL + (newStateURL.indexOf('?') === -1 ? '?' : '&') + 'partial=1',
            '', function() {
            $(document).trigger('contentLoad');
            $paginated.css({opacity: 1.0});
            var scrollDown = Boolean($(document).scrollTop() > $paginated.offset().top);
            if ($paginated.is(':hidden')) {
                $('.show_paginated_div').hide()
                $('#paginated_wrapped').show();
                scrollDown = true;
            }
            if (scrollDown) {
                $('html,body').animate({scrollTop: $paginated.offset().top - 15});
            }
        }).css({opacity: 0.6});

        // Tell Google Analytics about the new hit
        if (typeof window._gaq !== 'undefined') {
            var relativeURL = '/' + newStateURL.replace(History.getRootUrl(), '');
            window._gaq.push(['_trackPageview', relativeURL]);
        }
    });

    var hash = History.getHash();
    if (hash && (hash.indexOf('/') !== -1 || hash.indexOf('?') !== -1)) {
//        $(window).trigger('statechange')
        window.location.assign(History.getState().url);
    }

});