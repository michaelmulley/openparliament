(function () {
  
  var $element,
    $anchor,
    $statement;

  $('body').on('click', '.statement .sharing-tools', function(e) {
    e.preventDefault();
    $element = $('#sharing-tools-dropdown');

    if ($element.hasClass('is-open')) {
      _closeDropdown();
      if ($anchor[0] === e.target) {
        // If the user clicked the same link used to originally open,
        // toggle off. Otherwise, reposition and reopen.
        return;
      }
    }
    $anchor = $(e.target);
    $statement = $anchor.closest('.statement');
    _setDropdownPosition();
    _setDropdownContent();
    $element.addClass('is-open');
    _addDropdownBodyHandler();
  });

  var _setDropdownPosition = function() {
    // First, try positioning the dropdown to the bottom left of the anchor.
    $element
      .css({'width': '400px', 'height': 'auto'})
      .offset(Foundation.Box.GetOffsets($element, $anchor, 'right bottom', 1, 1));

    if (!Foundation.Box.ImNotTouchingYou($element, null, true)) {
      // If that doesn't work, set it to screen width
      $element
        .css({'width': Foundation.Box.GetDimensions($element).windowDims.width - 2})
        .offset(Foundation.Box.GetOffsets($element, $anchor, 'center bottom', 1, 1, true));
    }
  };

  var _addDropdownBodyHandler = function() {
    $(document.body)
      .off('click.statement-sharing-dropdown')
      .on('click.statement-sharing-dropdown', function(e) {
        if ($element.is(e.target) || $element.find(e.target).length)
          return;
        if ($anchor.is(e.target) || $anchor.find(e.target).length)
          return;
        _closeDropdown();
        $(document.body).off('click.statement-sharing-dropdown');
      });
  };

  var _closeDropdown = function () {
      $element.removeClass('is-open').removeClass('copy-success');
  };

  var _setDropdownContent = function() {
    if (!$element.data('events-added'))
      _addDropdownEvents();
      $element.data('events-added', true);

    // Share textbox URL
    $element.find('input.statement-url').val(OP.BASE_URL + $statement.attr('data-url'));

    var statementid = $statement.attr('data-hocid');
    if (statementid && /^\d+$/.test(statementid)) {
      // Only statement IDs that are just digits are actually original, so only use those
      var parldocurl = $('a[data-hoc-doc-url]').attr('href');    
      if (parldocurl) {
        var parlstateurl = parldocurl + '#Int-' + statementid;
      }
      else {
        var parlstateurl = $statement.attr('data-url') + 'parl-redirect/';
      }
      $element.find('.parl-links').show().find('.transcript').attr('href', parlstateurl);
      $element.find('.parl-links .video').attr('href', 
        'https://www.ourcommons.ca/embed/' + OP.LANG.toLowerCase() + '/i/' + statementid + '?ml='
        + OP.LANG.toLowerCase() + '&vt=watch');
    }
    else {
      $element.find('.parl-links').hide();
    }
  }

  var _addDropdownEvents = function() {
    var _statementDescription = function() {
      var descr = $statement.find('.pol_name').text();
      var topic = $statement.find('.statement_topic').text();
      if (topic) {
        descr += ' on ' + topic;
      }
      return descr;
    };

    $element.on('click', '.twitter', function(e) {
      e.preventDefault();
      OP.utils.openShareWindow('https://twitter.com/share?'
        + $.param({'url': $element.find('.statement-url').val(),
        'via': 'openparlca',
        'related': 'openparlca:openparliament.ca',
        'text': _statementDescription()
      }));
    })
    .on('click', '.facebook', function(e) {
      e.preventDefault();
      OP.utils.openShareWindow('https://facebook.com/sharer.php?'
        + $.param({'u': $element.find('.statement-url').val(),
        't': _statementDescription()}));
    })
    .on('click', '.statement-url-group', function(e) {
      e.preventDefault();
      var manual_copy = function() {
        window.prompt(
          "To copy, press Ctrl-C (Command-C on Mac), then Enter",
          $element.find('.statement-url').val()
        );
      };
      try {
        $element.find('.statement-url').select();
        if (document.execCommand('copy')) {
          $element.addClass('copy-success');
        }
        else {
          manual_copy();
        }
      } catch (err) {
        manual_copy()
      }
    });
  };

}());