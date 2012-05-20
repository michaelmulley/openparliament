OP = {};

function rot13 (t){
        return t.replace(/[a-z0-9]/ig, function(chr) {
            var cc = chr.charCodeAt(0);
            if (cc >= 65 && cc <= 90) cc = 65 + ((cc - 52) % 26);
            else if (cc >= 97 && cc <= 122) cc = 97 + ((cc - 84) % 26);
            else if (cc >= 48 && cc <= 57) cc = 48 + ((cc - 43) % 10);
            return String.fromCharCode(cc);
        });
}
function openparlShareWindow(url) {
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
}
$(function() {
    $('body').addClass('js');

    // SEARCH BUTTONS
    var searchbox_default = 'Search';
    $('#nav_searchbox').val(searchbox_default).bind('focus', function() {
       $(this).addClass('active'); 
       if (this.value == searchbox_default) {
           this.value = '';
       }
    }).bind('blur', function () {
       $(this).removeClass('active');
       if (this.value == '') {
           this.value = searchbox_default;
       }
    });
    $('#nav_searchform').bind('submit', function(e) {
        var v = $('#nav_searchbox').val();
        if (v == searchbox_default || v == "") {
            e.preventDefault();
            alert("To search, enter a postal code, name, or phrase into the text box.");
        }
    });
    $('#nav_searchbutton').click(function(e) {
       e.preventDefault();
       $('#nav_searchform').submit();
    });

    // TOOLTIPS
    jQuery.fn.overflowtip = function() {
        return this.each(function() {
            if (this.clientWidth < this.scrollWidth 
              || (this.clientHeight + 5) < this.scrollHeight) {
                $(this).attr('title', $(this).text());       
            }
        });
    }    
    $('.overflowtip').overflowtip().tooltip({delay: 150});
    $('.tip, .related_link').tooltip({delay: 100, showURL: false});
    
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
    
    $('a.maillink').attr('href', rot13('znvygb:zvpunry@zvpunryzhyyrl.pbz'));
    
    $('a[href$="#hl"]').each(function () {
        this.href = this.href.substring(0, this.href.length - 3);
    });
    
    var uservoiceOptions = {
      key: 'openparliament',
      host: 'openparliament.uservoice.com', 
      forum: '52385',
      lang: 'en',
      showTab: false
    };
    /* $('.feedback').click(function(e) {
        e.preventDefault();
        UserVoice.Popin.show(uservoiceOptions);
    }); */
   
});