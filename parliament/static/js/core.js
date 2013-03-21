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
    },

    notify: function(message, tag, opts) {
        /** Display a notification to the user.
         * tag should be 'warning', 'success', or 'error'
         * see defaults for options
         */
        tag = tag || 'warning';
        opts = opts || {};
        _.defaults(opts, {
            'animateIn': true,
            //'allowHTML': false,
            'hideAfter': (tag == 'error' ? 10000 : 5000) // # of milliseconds after which to hide the message, 0 to require manual close
        });
        var $target = $('#notifications');
        // if (!opts.allowHTML) {
        //     message = _.escape(message);
        // }

        var template = _.template('<div class="top-notification <%= tag %>"><div class="notification-inner">' +
        '<a href="#" class="close">&times;</a><%- message %></div></div>');
        var $el = $(template({ message: message, tag: tag}));
        if ($(document).scrollTop() > $target.offset().top) {
            if (!$('#fixed-notification-container').length) {
                $('body').append('<div id="fixed-notification-container"></div>');
            }
            $target = $('#fixed-notification-container');
        }
        if (opts.animateIn) {
            $el.hide();
        }
        $target.append($el);
        if (opts.animateIn) {
            $el.slideDown();
        }

        var close = function() {
            $el.find('a.close').click();
        };

        if (opts.hideAfter) {
            setTimeout(close, opts.hideAfter);
        }
        return { close: close};
    }
};

// https://developer.mozilla.org/en-US/docs/DOM/document.cookie
OP.cookies = {
    getItem: function (sKey) {
        if (!sKey || !this.hasItem(sKey)) { return null; }
        var ck = unescape(document.cookie.replace(new RegExp("(?:^|.*;\\s*)" + escape(sKey).replace(/[\-\.\+\*]/g, "\\$&") + "\\s*\\=\\s*((?:[^;](?!;))*[^;]?).*"), "$1"));
        if (ck.substr(0, 1) === '"' && ck.substr(-1, 1) === '"') {
            return ck.substr(1, ck.length-2);
        }
        return ck;
    },
    hasItem: function (sKey) {
        return (new RegExp("(?:^|;\\s*)" + escape(sKey).replace(/[\-\.\+\*]/g, "\\$&") + "\\s*\\=")).test(document.cookie);
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

if (window.Raven) {
    Raven.config('http://dd5ba91c44624714b48f16324b0301b3@sentry.oconnect.ca/3').install();
}

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
            $q.val($prepend.val() + ' ' + $q.val());
            $prepend.val('');
            $prepend.remove();
        }
    });
    $('input[name=q]').val('');

    $('body').delegate('.top-notification a.close', 'click', function(e) {
        var $notification = $(this).closest('.top-notification');
        
        $notification.slideUp(function() {
            $notification.remove(); // We won't need it again after it's been closed
        });
    });
    
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