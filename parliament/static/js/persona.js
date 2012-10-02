OP.auth = {

    personaInitialized: false,

    initializePersona: function() {
        var init = function() {
            navigator.id.watch({
                loggedInUser: OP.auth.authenticatedEmail,
                onlogin: function(assertion) {
                    $.ajax({ 
                        type: 'POST',
                        url: '/accounts/login/',
                        data: {assertion: assertion},
                        success: function(res, status, xhr) { window.location.reload(); },
                        error: function(res, status, xhr) { alert("login failure" + res); }
                    });
                },
                onlogout: function() {
                    $.ajax({
                        type: 'POST',
                        url: '/accounts/logout/',
                        success: function() { window.location.reload(); },
                        error: function (res, status, xhr) {
                            alert("logout failure" + res);
                        }
                    });
                }
            });
            OP.auth.personaInitialized = true;
        };

        if (_.isUndefined(OP.auth.authenticatedEmail)) {
            $.getJSON('/accounts/current/', function(data) {
                OP.auth.authenticatedEmail = data.content;
                init();
            });
        }
        else {
            init();
        }
    },

    callPersona: function(callback) {
        if (_.isUndefined(navigator.id)) {
            LazyLoad.js('https://login.persona.org/include.js', function() {
                OP.auth.initializePersona();
                callback();
            });
        }
        else {
            if (!OP.auth.personaInitialized) {
                OP.auth.initializePersona();
            }
            callback();
        }
    },

    login: function() {
        OP.auth.callPersona(function() {
            navigator.id.request({
            // siteLogo: "{{ STATIC_URL }}images/o60.png"
            // siteName: "Open Parliament"
            });
        });
    },

    logout: function() {
        OP.auth.callPersona(function() {
            navigator.id.logout();
        });
    }

};

$(function() {
    $('body').delegate('a.persona-login', 'click', function(e) {
        e.preventDefault();
        OP.auth.login();
    }).delegate('a.persona-logout', 'click', function(e) {
        e.preventDefault();
        OP.auth.logout();
    });

    if ($('a.persona-logout,a.persona-login').length) {
        // If there's a sign in/out button on the page, we need to load the Persona JS right away.
        OP.auth.callPersona(function() {}); 
    }

    $(document).ajaxError(function(event, jqXHR, ajaxSettings, thrownError) {
        if (jqXHR.getResponseHeader('X-OP-Login-Required')) {
            OP.auth.login();
        }
        else if (jqXHR.getResponseHeader('X-OP-Redirect')) {
            window.location.pathname = jqXHR.getResponseHeader('X-OP-Redirect');
        }
    });
});