$(document).foundation();

$(function() {
	if (window.Raven) {
	    Raven.config(
	        'https://b5fd50dac5844b9a872b9fb5718ae980@sentry.io/113972',
	        {
	            whitelistUrls: [ /openparliament\.ca/ ],
	            ignoreUrls: [  /extensions\//i, /^chrome:\/\//i ]
	        }
	    ).install();
	}

	$('#navbar-buttons-search').click(function(e) {
		e.preventDefault();
		var $searchbar = $('#navbar-search');
		if ($searchbar.is(':visible')) {
			$searchbar.slideUp('fast');
			$('#navbar-buttons-search').removeClass('active');
		}
		else {
			$searchbar.slideDown('fast', function() {
				$searchbar.find('input').focus();
				$('#navbar-buttons-search').addClass('active');
			});
		}
	});
});