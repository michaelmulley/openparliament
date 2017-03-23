(function() {

    var revealStatement =  function () {
        $(this).hide()
            .parent().animate({
                maxHeight: '800px'
            }, 'fast', 'linear',
            function () {
                $(this).addClass('displayall').css('max-height', 'none').removeClass('truncated');
            });
    };

    $(document).bind('contentLoad', function() {
        if ($('.statement_browser').length && !$('.disable_more_links').length) {
            $('.statement .main-col:not(.truncated)').each(function() {
                if (this.clientHeight < this.scrollHeight) {
                    $(this).addClass('truncated');
                    var $morelink = $(document.createElement('div')).html('&darr;').addClass('morelink').click(revealStatement);
                    // var $fadeout = $(document.createElement('div')).addClass('fadeout');
                    $(this).prepend($morelink);
                }
            });
        }
    });

})();