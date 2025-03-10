/////////
/// Checks if we should reload full page withot caches
/////////
var shouldReloadPage = false;
$(() => {
    $(".should-reload-page-on-change").on( "change", () => {
        shouldReloadPage = true;
    });
})

/////////
/// An API Call and page Reload Function
/////////
function apiCallAndReload(query_params, body, errorCallback) {
    const query_params_str = new URLSearchParams(query_params).toString()
    const body_str = body !== null ? JSON.stringify(body) : null
    $.ajax({
        url:  `${window.location.pathname}?${query_params_str}`,
        type: 'POST',
        data: body_str,
        contentType: 'application/json',
        headers: {
            Accept: 'application/json'
        },
        success: () => {
            if (shouldReloadPage) {
                location.replace(location.pathname);
                return
            }
            location.reload()
        },
        error: (request) => {
            /// Redirect to auth url if token expired
            if (request.responseJSON.hasOwnProperty('auth_url')) {
                location.replace(request.responseJSON.auth_url);
                return
            }

            /// Error - show error
            $('#there-was-en-error').removeClass('d-none');
            if (request.responseJSON.hasOwnProperty('error') && request.responseJSON.error && request.responseJSON.hasOwnProperty('detail')) {
                $('#there-was-en-error').text(request.responseJSON.detail);
            }

            errorCallback();
        }
    });
}


/////////
/// Gettings and atemping to resend request after login
/////////
$(() => {
    postLoginBodyState = Cookies.get('PostLoginBodyState')
    let onErrorFunction = () => {
        $("error-could-not-restore-previous-api-call").removeClass('d-none');
        $('#there-was-en-error').addClass('d-none');
    }
    if (postLoginBodyState !== undefined) {
        $.ajax({
            url:  `/login/restore/${postLoginBodyState}`,
            type: 'GET',
            success: (responce) => {
                Cookies.remove('PostLoginBodyState')

                /// Make a save call and reload page
                apiCallAndReload(responce.query_params, responce.body, onErrorFunction)
                
            },
            error: onErrorFunction
        });
    }
})