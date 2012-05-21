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
    if ($('.statement_browser').length && !$('.disable_more_links').length) {
        addMoreLinks();
    }
    var $paginated = $('#paginated');
    $('.pagelink').live('click', function(e) {
        e.preventDefault();
        var $pagelink = $(this);
        History.pushState(null, null, this.href);
        if ($pagelink.hasClass('show_paginated_div')) {
            $(this).html('Loading...');
        }
        $paginated.find('.pagination').addClass('loading');
    });

    $(window).bind('statechange', function(e) {
        var newStateURL = History.getState().url;
        $paginated.find('.pagination').addClass('loading');
        $paginated.load(newStateURL, '', function() {
            $paginated.css({opacity: 1.0});
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
        }).css({opacity: 0.6});
    });

    var hash = History.getHash();
    if (hash && (hash.indexOf('/') !== -1 || hash.indexOf('?') !== -1)) {
//        $(window).trigger('statechange')
        window.location.assign(History.getState().url);
    }

    /* STATEMENT SHARING BUTTONS */
    
    if (!$('body').hasClass('search')) {
        var $statementTools = $('<div id="statement-tools" style="display: none"><img id="share_link" src="/static/images/link.png" class="tip" title="Share a link to this statement"><img id="share_twitter" src="/static/images/twitter.png" class="tip" alt="Twitter" title="Share on Twitter"><img id="share_facebook" src="/static/images/facebook.png" class="tip" title="Share on Facebook"></div>');
        $statementTools.bind('mouseenter', function () {$statementTools.show();})
            .bind('mouseleave', function () {$statementTools.hide();})
            .find('.tip').tooltip({delay: 100, showURL: false});
        $paginated.after($statementTools);
        var $currentStatement;
        function currentStatementURL() {
            return 'http://openparliament.ca' + $currentStatement.attr('data-url');
        }
        function currentStatementDescription() {
            var descr = $currentStatement.find('.pol_name').html();
            if (!descr) {
                descr = $('.pol_name').html();
            }
            var topic = $currentStatement.find('.statement_topic').html();
            if (topic) {
                descr += ' on ' + topic;
            }
            return descr;
        }
        $('.statement').live('mouseenter', function() {
            $currentStatement = $(this);
            var offset = $currentStatement.position();
            $statementTools.css({'top': offset.top, 'left': offset.left + ($currentStatement.width() - 66)}).show();
        }).live('mouseleave', function() {$statementTools.hide();});
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
            OP.utils.openShareWindow('http://facebook.com/sharer.php?'
                + $.param({'u': currentStatementURL(),
                't': currentStatementDescription()}));
        });
        $('#share_twitter').click(function() {
            OP.utils.openShareWindow('http://twitter.com/share?'
                + $.param({'url': currentStatementURL(),
                'via': 'openparlca',
                'related': 'openparlca:openparliament.ca',
                'text': currentStatementDescription()
                }));
        });
    }
});