(function() {

  /* SEE MORE */
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
      $('.statement .text-col:not(.truncated)').each(function() {
        if (this.clientHeight < this.scrollHeight) {
          $(this).addClass('truncated');
          var $morelink = $(document.createElement('div')).html('&darr;').addClass('morelink').click(revealStatement);
          $(this).prepend($morelink);
        }
      });
    }

    $('.statement_browser.statement').each(function() { displayLanguageStatus(this); });
  });


  /* LANGUAGE CONTROL */
  var LANG_STATUSES = {
    PARTIALLY_TRANSLATED: 'Partially translated',
    FLOOR: 'As spoken',
    TRANSLATED: 'Translated'
  };

  var _determineLanguageStatus = function(statement) {
    var paragraphs = $(statement).find('p[data-originallang]').get();
    var langs = _.uniq(_.map(paragraphs, function(p) { return p.getAttribute('data-originallang'); }));
    if (langs.length == 0)
      return 'NONE';
    if (langs.length == 2)
      return 'PARTIALLY_TRANSLATED';
    if (langs.length == 1) {
      if (langs[0] === OP.LANG)
        return 'FLOOR';
      return 'TRANSLATED'
    }
  };

  var getLanguageStatus = function(statement) {
    var lang_status = statement.getAttribute('data-languagestatus');
    if (!lang_status) {
      lang_status = _determineLanguageStatus(statement);
      statement.setAttribute('data-languagestatus', lang_status);
      if (statement.getAttribute('data-floor'))
        $(statement).addClass('lang-switchable');
    }
    return lang_status;
  };

  var displayLanguageStatus = function(statement) {
    var lang_status = getLanguageStatus(statement);
    if (lang_status && lang_status !== 'NONE') {
      $(statement).find('.lang-control').text(LANG_STATUSES[lang_status]);
    }        
  }

  var switchLanguage = function(statement) {
    if (statement.getAttribute('data-languagestatus') === 'FLOOR') {
      if (!$(statement).data('original_lang_status'))
        throw(new Error("original data attributes not available in switchLanguage"));
      switchLanguageContent(statement, $(statement).data('original_paragraphs'),
        $(statement).data('original_lang_status'));
    }
    else {
      switchLanguageToFloor(statement);
    }
  };

  var switchLanguageToFloor = function(statement) {
    var paragraphs = $(statement).find('.text p').get();
    $(statement).data('original_paragraphs', paragraphs);
    $(statement).data('original_lang_status', statement.getAttribute('data-languagestatus'));
    var paragraphs_floor = $(statement.getAttribute('data-floor')).get();
    switchLanguageContent(statement, paragraphs_floor, 'FLOOR');
  }

  var switchLanguageContent = function(statement, new_content, new_status) {
    var $text = $(statement).find('div.text');
    $text.children().remove();
    $text.append(new_content);
    statement.setAttribute('data-languagestatus', new_status);
    displayLanguageStatus(statement);
  }

  $('body').on('click', '.lang-switchable .lang-control', function(e) {
    e.preventDefault();
    var statement = $(e.target).closest('.statement').get()[0];
    switchLanguage(statement);
  });

})();