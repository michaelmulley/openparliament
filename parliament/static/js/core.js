OP = {};

OP.badIE = ($.browser.msie && parseInt($.browser.version, 10) < 9);

OP.utils = {

    rot13: function (t){
        return t.replace(/[a-z0-9]/ig, function(chr) {
            var cc = chr.charCodeAt(0);
            if (cc >= 65 && cc <= 90) cc = 65 + ((cc - 52) % 26);
            else if (cc >= 97 && cc <= 122) cc = 97 + ((cc - 84) % 26);
            else if (cc >= 48 && cc <= 57) cc = 48 + ((cc - 43) % 10);
            return String.fromCharCode(cc);
        });
    },

    openShareWindow: function(url) {
        var width = 550;
        var height = 450;
        var left = Math.round((screen.width / 2) - (width / 2));
        var top = 0;
        if (screen.height > height) {
            top = Math.round((screen.height / 2) - (height / 2));
        }
        window.open(url, "openparliament_share", "width=" + width +
            ",height=" + height + ",left=" + left, ",top=" + top +
            "personalbar=no,toolbar=no,scrollbars=yes,location=yes,resizable=yes");
    },

    getQueryParam: function(name, qs) {

        if (!qs) {
            qs = window.location.search;
        }
        else {
            qs = '?' + qs.split('?')[1];
        }

        var match = RegExp('[?&]' + name + '=([^&]*)')
            .exec(qs);

        return match && decodeURIComponent(match[1].replace(/\+/g, ' '));

    },

    slugify: function(s) {
        return s.toLowerCase().replace(/[^a-z0-9]/, '-');
    }
};

// TOOLTIPS
jQuery.fn.overflowtip = function() {
    return this.each(function() {
        if (this.clientWidth < this.scrollWidth
            || (this.clientHeight + 5) < this.scrollHeight) {
            $(this).attr('title', $(this).text());
        }
    });
};

$(function() {

    // MARGINALIA
    var $content = $('#content');
    var contentOffset = $content.offset();
    $.fn.marginalia = function(onEvent, offEvent, dataFunction) {
        if (this.length) {
            var $marginalia = $('#marginalia');
            if (!$marginalia.length) {
                $marginalia = $('<div id="marginalia"></div>');
                $marginalia.appendTo($('#content'));
            }
            $marginalia.hide();
            this.bind(onEvent, function() {
                var $this = $(this);
                var content = dataFunction($this);
                if (content) {
                    $marginalia.html(content);
                    $marginalia.css({'top': ($this.offset().top - contentOffset.top) + 'px'}).show();
                }
            }).bind(offEvent, function() { $marginalia.hide(); });
        }
    };
    
    $('.standard_form input, .standard_form textarea').marginalia('focus', 'blur',
        function($obj) { return $obj.attr('data-helptext');});

    $('[data-marginalia]').marginalia('mouseenter', 'mouseleave', function($obj) {
        return $obj.attr('data-marginalia');
    });

    $('body').removeClass('nojs').addClass('js');

    $('.overflowtip').overflowtip().tooltip({delay: 150});

    // Search forms: if there's an automatic "prepend" value,
    // stick it onto the query then get rid of it.
    $('form.prepender').submit(function(e) {
        var $prepend = $(this).find('input[name=prepend]');
        if ($prepend.val()) {
            var $q = $(this).find('input[name=q]');
            $q.val($prepend.val() + ' ' + $q.val())
            $prepend.val('');
            $prepend.remove();
        }
    });
    $('input[name=q]').val('');

    // This event is to be triggered on AJAX loads too
    $(document).bind('contentLoad', function() {
        $('.tip, .related_link').tooltip({delay: 100, showURL: false});

        $('a.maillink').attr('href', OP.utils.rot13('znvygb:zvpunry@zvpunryzhyyrl.pbz'));

        $('a[href$="#hl"]').each(function () {
            this.href = this.href.substring(0, this.href.length - 3);
        });
    });

    $(document).trigger('contentLoad');

//    var uservoiceOptions = {
//      key: 'openparliament',
//      host: 'openparliament.uservoice.com',
//      forum: '52385',
//      lang: 'en',
//      showTab: false
//    };

});