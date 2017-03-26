$(function() {
	if (!window.localStorage) return;

	var now = new Date().getTime();
	var KEY = 'op_province';
	var province = null;

	var save_province = function(province) {
		var expires = now + (60 * 60 * 24 * 20);
		try {
			window.localStorage.setItem(KEY, expires + ',' + province);
		}
		catch (error) {
			// iOS loves throwing localStorage errors, e.g. whenever in private browsing
			return false;
		}
	};

	var show_province_alert = function(province) {
		var msg = null;
		if (province == 'NS') {
			msg = 'Are you in Nova Scotia? Visit <a href="http://www.openhousens.ca/">OpenHouseNS</a> for the latest from your provincial legislature.';
		}
		else if (province == 'NT') {
			msg = 'Are you in the Northwest Territories? Visit <a href="http://hansard.opennwt.ca/">OpenNWT</a> for the latest from your territorial legislature.';
		}
		if (msg) {
			OP.utils.notify(msg, 'success', {
				animateIn: false,
				hideAfter: 0,
				allowHTML: true,
				onClose: function() {save_province('NO');}
			});
		}
	};

	var stored = null;
	try {
		stored = window.localStorage.getItem(KEY);
	}
	catch (err) {}

	if (stored) {
		stored = stored.split(',');
		if (now < parseInt(stored[0], 10)) {
			province = stored[1];
		}
	}

	if (province) {
		return show_province_alert(province);
	}

	$.getJSON('https://freegeoip.tahini.michaelmulley.com/json/', function(data) {
		if (data) {
			if (data.country_code == 'CA' && data.region_code) {
				save_province(data.region_code);
				show_province_alert(data.region_code);
			}
			else if (data.country_code) {
				save_province('NO');
			}
		}
	});
})