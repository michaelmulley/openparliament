OP.auth = {

    personaInitialized: false,

    personaLogoutTimeout: false,

    authenticatedEmail: OP.cookies.getItem('email'),

    initializePersona: function() {
        navigator.id.watch({
            loggedInUser: OP.auth.authenticatedEmail,
            onlogin: function(assertion) {
                $.ajax({
                    type: 'POST',
                    url: '/accounts/login/',
                    data: {assertion: assertion},
                    success: function(res, status, xhr) { window.location.reload(); },
                    error: function(res, status, xhr) {
                        OP.utils.notify("Oops! There was a problem logging you in.", 'error');
                    }
                });
            },
            onlogout: function() {
                OP.auth.localLogout();
            }
        });
        OP.auth.personaInitialized = true;
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
        // At the moment, logout can fail silently if third-party cookies are disabled.
        // Use this workaround
        OP.auth.personaLogoutTimeout = window.setTimeout(OP.auth.localLogout, 1000);
        OP.auth.callPersona(function() {
            navigator.id.logout();
        });
    },

    localLogout: function() {
        if (OP.auth.personaLogoutTimeout) {
            window.clearTimeout(OP.auth.personaLogoutTimeout);
            OP.auth.personaLogoutTimeout = false;
        }
        $.ajax({
            type: 'POST',
            url: '/accounts/logout/',
            success: function() { window.location.reload(); },
            error: function (res, status, xhr) {
                OP.utils.notify("Oops! There was a problem logging you out.", 'error');
            }
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

    if ($('a.persona-logout,a.persona-login').length || !_.isUndefined(navigator.id)) {
        // If there's a sign in/out button on the page, we need to load the Persona JS right away.
        OP.auth.callPersona(function() {});
    }

    $(document).ajaxError(function(event, jqXHR, ajaxSettings, thrownError) {
        if (jqXHR.getResponseHeader('X-OP-Login-Required')) {
            OP.auth.login();
        }
        else if (jqXHR.getResponseHeader('X-OP-Redirect')) {
            window.location.href = jqXHR.getResponseHeader('X-OP-Redirect');
        }
    });
});