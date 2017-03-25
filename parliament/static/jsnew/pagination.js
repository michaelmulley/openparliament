$(function() {

    var last_navigated_url = null;

    $('body').on('click', '.pagination a', function(e) {
        e.preventDefault();
        if (this.href) {
            window.history.pushState(null, null, this.href);
            if ($(this).hasClass('show_paginated_div')) {
                $(this).html('Loading...');
            }
            $('#paginated').find('.pagination').addClass('loading');
            window.OP.AJAXNavigate(this.href);
        }
    });

    $(window).on('popstate', function(e) {
        window.OP.AJAXNavigate(document.location.href);
    });

    var getURLParts = function(url) {
        var a = document.createElement('a');
        a.href = url;

        return {
            href: a.href,
            host: a.host,
            hostname: a.hostname,
            port: a.port,
            pathname: a.pathname,
            protocol: a.protocol,
            hash: a.hash,
            search: a.search
        };
    };

    window.OP.AJAXNavigate = function(url) {
        last_navigated_url = url;
        var $paginated = $('#paginated');
        $paginated.find('.pagination').addClass('loading');
        $paginated.load(url + (url.indexOf('?') === -1 ? '?' : '&') + 'partial=1',
            '', function() {
            $paginated.css({opacity: 1.0});
            $(document).trigger('contentLoad');
            var scrollDown = Boolean($(document).scrollTop() > $paginated.offset().top);
            if ($paginated.is(':hidden')) {
                $('.show_paginated_div').hide()
                $('#paginated_wrapped').show();
                scrollDown = true;
            }
            if (scrollDown) {
                $('html,body').animate({scrollTop: $paginated.offset().top - 15});
            }
        });

        $paginated.css({opacity: 0.5});

        // Tell Google Analytics about the new hit
        if (typeof window._gaq !== 'undefined') {
            var urlParts = getURLParts(url);
            var relativeURL = urlParts.pathname + urlParts.search;
            window._gaq.push(['_trackPageview', relativeURL]);
        }
    };


});