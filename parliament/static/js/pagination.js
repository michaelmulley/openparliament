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
                    $('#paginated_wrapped').show();
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
    
    /* STATEMENT SHARING BUTTONS */
    
    if (!$('body').hasClass('search')) {
        var $statementTools = $('<div id="statement-tools" style="display: none"><img id="share_link" src="/static/images/link.png" class="tip" title="Share a link to this statement"><img id="share_twitter" src="/static/images/twitter.png" class="tip" alt="Twitter" title="Share on Twitter"><img id="share_facebook" src="/static/images/facebook.png" class="tip" title="Share on Facebook"></div>');
        $statementTools.find('.tip').tooltip({delay: 100, showURL: false});
        $paginated.after($statementTools);
        var $currentStatement;
        function currentStatementURL() {
            return 'http://openparliament.ca' + $currentStatement.attr('data-url');
        }
        $('.statement').live('mouseenter', function() {
            $currentStatement = $(this);
            var offset = $currentStatement.offset();
            $statementTools.css({'top': offset.top, 'left': offset.left + ($currentStatement.width() - 66)}).show();
        });
        $('#share_link').click(function() {
            if (!$currentStatement.find('.share_link').length) {
                var linkbox = $('<input type="text">').val(currentStatementURL()).click(function() {
                    if (this.createTextRange) {
                        // This is for IE and Opera.
                        range = this.createTextRange();
                        range.moveEnd('character', this.value.length);
                        range.select();
                    } else if (this.setSelectionRange) {
                        // This is for Mozilla and WebKit.
                        this.setSelectionRange(0, this.value.length);
                    }});
                $currentStatement.find('.focus').prepend($('<p class="share_link">Copy this link: </p>').append(linkbox));
            }
        });
        $('#share_facebook').click(function() {
            window.open('http://facebook.com/sharer.php?'
                + $.param({'u': currentStatementURL(),
                't': $currentStatement.find('.pol_name').html() + ' on ' + $currentStatement.find('.statement_topic').html()}));
        });
        $('#share_twitter').click(function() {
            window.open(currentStatementURL() + 'twitter/');
        });
    }
});