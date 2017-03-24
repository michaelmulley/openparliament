(function () {
  // Hackily assembled from foundation.dropdown.js, which doesn't support multiple anchors
  // for the same dropdown. Most of the code here is probably unnecessary.
  
  var $element,
    $anchor,
    $statement;
  $('body').on('click', '.statement h6.sharing-tools', function(e) {
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

  var _vOffset = 1,
    _hOffset = 1,
    _dropdownCounter = 4,
    _usedPositions = [];

  var _setDropdownPosition = function($parent) {
    // if(this.$anchor.attr('aria-expanded') === 'false'){ return false; }
    var position = 'right bottom',
        $eleDims = Foundation.Box.GetDimensions($element),
        $anchorDims = Foundation.Box.GetDimensions($anchor),
        direction = (position === 'left' ? 'left' : ((position === 'right') ? 'left' : 'top')),
        param = (direction === 'top') ? 'height' : 'width',
        offset = (param === 'height') ? _vOffset : _hOffset;

    if(($eleDims.width >= $eleDims.windowDims.width) || (!_dropdownCounter && !Foundation.Box.ImNotTouchingYou($element, $parent))){
      var newWidth = $eleDims.windowDims.width,
          parentHOffset = 0;
      if($parent){
        var $parentDims = Foundation.Box.GetDimensions($parent),
            parentHOffset = $parentDims.offset.left;
        if ($parentDims.width < newWidth){
          newWidth = $parentDims.width;
        }
      }

      $element.offset(Foundation.Box.GetOffsets($element, $anchor, 'center bottom', _vOffset, _hOffset + parentHOffset, true)).css({
        'width': newWidth - (_hOffset * 2),
        'height': 'auto'
      });
      // this.classChanged = true;
      return false;
    }

    $element.offset(Foundation.Box.GetOffsets($element, $anchor, position, _vOffset, _hOffset));

    while(!Foundation.Box.ImNotTouchingYou($element, null, true) && _dropdownCounter){
      _dropdownReposition(position);
      _setDropdownPosition($parent);
    }
  };

  var _dropdownReposition = function(position) {
    _usedPositions.push(position ? position : 'bottom');
    //default, try switching to opposite side
    if(!position && (_usedPositions.indexOf('top') < 0)){
      $element.addClass('top');
    }else if(position === 'top' && (_usedPositions.indexOf('bottom') < 0)){
      $element.removeClass(position);
    }else if(position === 'left' && (_usedPositions.indexOf('right') < 0)){
      $element.removeClass(position)
          .addClass('right');
    }else if(position === 'right' && (_usedPositions.indexOf('left') < 0)){
      $element.removeClass(position)
          .addClass('left');
    }

    //if default change didn't work, try bottom or left first
    else if(!position && (_usedPositions.indexOf('top') > -1) && (_usedPositions.indexOf('left') < 0)){
      $element.addClass('left');
    }else if(position === 'top' && (_usedPositions.indexOf('bottom') > -1) && (_usedPositions.indexOf('left') < 0)){
      $element.removeClass(position)
          .addClass('left');
    }else if(position === 'left' && (_usedPositions.indexOf('right') > -1) && (_usedPositions.indexOf('bottom') < 0)){
      $element.removeClass(position);
    }else if(position === 'right' && (_usedPositions.indexOf('left') > -1) && (_usedPositions.indexOf('bottom') < 0)){
      $element.removeClass(position);
    }
    //if nothing cleared, set to bottom
    else{
      $element.removeClass(position);
    }
    // this.classChanged = true;
    _dropdownCounter--;
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

    var parldocurl = $('a[data-hoc-doc-url]').attr('href');
    var statementid = $statement.attr('data-hocid');
    if (parldocurl && statementid) {
      $element.find('.parl-links').show().find('.transcript').attr('href', parldocurl + '#Int-' + statementid);
      $element.find('.parl-links .video').attr('href', 
        'http://parlvu.parl.gc.ca/Embed/' + OP.LANG.toLowerCase() + '/i/' + statementid + '?ml='
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
    .on('click', '.copy-statement-url', function(e) {
      e.preventDefault();
      $element.find('.statement-url').select();
      var manual_copy = function() {
        window.prompt(
          "To copy, press Ctrl-C (Command-C on Mac), then Enter",
          $element.find('.statement-url').val()
        );
      };
      try {
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