(function() {

  /* SEE MORE */
  var revealStatement =  function () {
    $(this).hide()
      .parent().animate({
        maxHeight: '800px'
      }, 'fast', 'linear',
      function () {
        $(this).addClass('displayall').css('max-height', 'none').removeClass('truncated');
        sessionStorage.setItem('expansion-' + this.dataset.id, 'expanded');
      });
  };

  // Reveal all truncated statements when Ctrl+F is pressed, so that they can be searched
  // ideally this'd cover other ways of opening the search box, or mobile,
  // but I don't know how to do that
  document.addEventListener('keydown', function (event) {
    if ((event.ctrlKey || event.metaKey) && event.key === 'f') {
        $('.statement .text-col.truncated').each(function() {
          $(this).addClass('displayall').removeClass('truncated');
        });
    }
  });

  $(document).bind('contentLoad', function() {
    $('.statement_browser.statement').each(function() { displayLanguageStatus(this); });
    if (TRANSLATE_PREFERENCE === 'NEVER') {
      switchAllLanguages('NEVER');
    }

    if ($('.statement_browser').length && !$('.disable_more_links').length) {
      $('.statement .text-col:not(.truncated)').each(function() {
        if (this.clientHeight < this.scrollHeight) {
          if (this.dataset.id && sessionStorage.getItem('expansion-' + this.dataset.id) === 'expanded') {
            $(this).addClass('displayall').removeClass('truncated');
          }
          else {
            $(this).addClass('truncated');
            var $morelink = $(document.createElement('div')).html('&darr;').addClass('morelink').click(revealStatement);
            $(this).prepend($morelink);
          }
        }
      });
    }

  });


  /* LANGUAGE CONTROL */
  var TRANSLATE_PREFERENCE = 'ERROR';
  try {
    if (window.localStorage.getItem('op_translate') == 'NEVER') {
      TRANSLATE_PREFERENCE = 'NEVER';
    }
    else {
      TRANSLATE_PREFERENCE = 'ALWAYS';
    }
  }
  catch (err) {}
  var saveTranslatePreference = function(mode) {
    try {
      window.localStorage.setItem('op_translate', mode);
      TRANSLATE_PREFERENCE = mode;
    }
    catch (err) {
      TRANSLATE_PREFERENCE = 'ERROR';
    }
  }
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
    if (langs.length >= 2)
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
      var floor = statement.getAttribute('data-floor');
      if (floor && floor.length > 9)
        $(statement).addClass('lang-switchable');
    }
    return lang_status;
  };

  var displayLanguageStatus = function(statement) {
    var lang_status = getLanguageStatus(statement);
    if (lang_status && lang_status !== 'NONE') {
      $(statement).find('.lang-control span').text(LANG_STATUSES[lang_status]);
    }        
  }

  var switchLanguage = function(statement) {
    if (statement.getAttribute('data-languagestatus') === 'FLOOR') {
      if (!$(statement).attr('data-original-languagestatus'))
        throw(new Error("original data attributes not available in switchLanguage"));
      switchLanguageContent(statement, $(statement).data('original_paragraphs'),
        $(statement).attr('data-original-languagestatus'));
      showLanguagePreferenceButton(statement, 'ALWAYS');
    }
    else {
      switchLanguageToFloor(statement);
      showLanguagePreferenceButton(statement, 'NEVER');
    }
  };

  var switchLanguageToFloor = function(statement) {
    var paragraphs = $(statement).find('.text p').get();
    $(statement).data('original_paragraphs', paragraphs);
    $(statement).attr('data-original-languagestatus', statement.getAttribute('data-languagestatus'));
    var floor = statement.getAttribute('data-floor');
    if (floor.length < 10) { return; }
    var paragraphs_floor = $(floor).get();
    switchLanguageContent(statement, paragraphs_floor, 'FLOOR');
  };

  var switchLanguageContent = function(statement, new_content, new_status) {
    var $text = $(statement).find('div.text');
    $text.children().remove();
    $text.append(new_content);
    statement.setAttribute('data-languagestatus', new_status);
    displayLanguageStatus(statement);
  };

  var showLanguagePreferenceButton = function(statement, mode) {
    // mode should be 'NEVER' or 'ALWAYS'
    var show = (mode !== TRANSLATE_PREFERENCE && TRANSLATE_PREFERENCE !== 'ERROR');
    $('.statement .lang-preference-switch').hide();
    if (show && statement) {
      $(statement).find('.lang-preference-switch span')
        .text(mode === 'ALWAYS' ? 'Always translate' : 'Never translate')
        .parent().attr('data-mode', mode)
        .show();
    }
  };

  var switchAllLanguages = function(mode) {
    var $states;
    if (mode === 'ALWAYS') {
      $states = $('.statement[data-original-languagestatus][data-languagestatus="FLOOR"]');
    }
    else {
      $states = $('.statement[data-languagestatus="TRANSLATED"],.statement[data-languagestatus="PARTIALLY_TRANSLATED"]');
    }
    $states.each(function() { switchLanguage(this); });
  };

  $('body')
    .on('click', '.lang-switchable .lang-control', function(e) {
      e.preventDefault();
      var statement = $(e.target).closest('.statement').get()[0];
      switchLanguage(statement);
    })
    .on('click', '.statement .lang-preference-switch', function(e) {
      var mode = $(this).attr('data-mode');
      saveTranslatePreference(mode);
      switchAllLanguages(mode);
      if (TRANSLATE_PREFERENCE === 'NEVER')
        OP.utils.notify("From now on, statements will appear in their original language across this site.", 'success');
    });

})();