/// HELPER FUNCTION: Split element`s id and make it nested objects
/// e.g. element with id settings-bot_my_name_plain-value and text 'value' would be
/// {settings: {bot_my_name_plain: {value: 'value'}}}
function set_request_data_from_id(id, set_value, curr_request_data) {
    id.split('-').forEach((value, index, array) => {
        if (index === array.length-1) {
            curr_request_data[value] = set_value
            return;
        }
        if (Object.hasOwn(curr_request_data, value) === false) {
            curr_request_data[value] = {};
        }
        curr_request_data = curr_request_data[value];
    })
}

/////////
/// Row edit and save button actions
/////////
$(() => {
    $('.row-edit, .row-save').click((elem) => {
        /// Check action - is it edditing start or saving after eddit
        const button = $(elem.delegateTarget);
        const button_edit_action = button.hasClass('row-edit');
        const button_save_action = button.hasClass('row-save');
        const button_icon = button.children()

        /// Toggle eddit and save statuses
        button.toggleClass('row-edit row-save');
        button.toggleClass('btn-outline-primary btn-outline-success');
        button_icon.toggleClass('bi-pencil-square bi-check2-square');

        /// Get row and tds to eddit
        const row = button.parent().parent()
        const editable_tds = row.children('.row-editable');
        const editable_inputs = editable_tds.children(':input');

        /// If action is to start an eddit - start an eddit
        if (button_edit_action) {
            editable_tds.addClass('table-info');
            editable_inputs.removeAttr('disabled');

            /// Replace new button with close button
            const close_button = $('.row-new, .row-close');
            const close_button_ico = close_button.children();
            close_button.removeClass('row-new btn-outline-secondary d-none');
            close_button_ico.removeClass('bi-plus-square');
            close_button.addClass('row-close');
            close_button.addClass('btn-outline-warning');
            close_button_ico.addClass('bi-slash-square');

            /// Remove new element
            $('.elem-new').addClass('d-none');

            /// Disable other eddit buttons
            $('.row-edit').attr('disabled', 'disabled');
        }

        /// If action is to save - parse data and make ajax call to an api
        if (button_save_action) {
            editable_tds.removeClass('table-info');
            editable_inputs.attr('disabled', 'disabled');

            /// Parse input data - make an object from array of elements
            const request_data = {}
            editable_inputs.each((index, elem) => {
                const jquery_elem = $(elem);
                set_request_data_from_id(jquery_elem.attr('id'), jquery_elem.val(), request_data);
            });

            /// Make a save call and reload page
            apiCallAndReload({}, request_data, () => {
                /// Error - remove eddit classes fro, buttons
                button.removeClass('row-edit');
                button.removeClass('btn-outline-primary');
                button_icon.removeClass('bi-pencil-square');

                /// Error - place save button
                button.addClass('row-save');
                button.addClass('btn-outline-success');
                button_icon.addClass('bi-check2-square');

                /// Error - only close button
                editable_tds.addClass('table-danger');
                editable_inputs.removeAttr('disabled');
            });
        }
    });
});


/////////
/// Row new or close button actions
/////////
$(() => {
    $('.row-new, .row-close').click((elem) => {
        /// Check action - is it create new element or close update
        const button = $(elem.delegateTarget);
        const button_new_action   = button.hasClass('row-new');
        const button_close_action = button.hasClass('row-close');

        $('.row-editable').children(':input').attr('disabled', 'disabled');
        $('.row-new-value').children(':input').removeAttr('disabled');

        /// Close action - reload page
        if (button_close_action) {
            location.reload();
        }

        /// Toggle eddit and save statuses
        button.toggleClass('row-new row-close');
        button.toggleClass('btn-outline-secondary btn-outline-warning');
        button.children().toggleClass('bi-plus-square bi-slash-square');

        /// New element - show it and disable eddit buttons
        if (button_new_action) {
            $('.elem-new').removeClass('d-none');
            $('.row-edit').attr('disabled', 'disabled');
        }
    });
});


/////////
/// Col edit and save button actions
/////////
$(() => {
    $('.col-edit, .col-save').click((elem) => {
        /// Check action - is it edditing start or saving after eddit
        const button = $(elem.delegateTarget);
        const button_edit_action = button.hasClass('col-edit');
        const button_save_action = button.hasClass('col-save');
        const button_icon = button.children()

        /// Toggle eddit and save statuses
        button.toggleClass('col-edit col-save');
        button.toggleClass('btn-outline-primary btn-outline-success');
        button_icon.toggleClass('bi-pencil-square bi-check2-square');

        /// Get col and tds to eddit
        const col_id = button.parent().attr('id');
        const editable_tds = $(`.${col_id}`);
        const editable_inputs = editable_tds.children(':input');

        /// If action is to start an eddit - start an eddit
        if (button_edit_action) {
            editable_tds.addClass('table-info');
            editable_inputs.removeAttr('disabled');

            /// Replace new button with close button
            const close_button = $('.col-new, .col-close');
            const close_button_ico = close_button.children();
            close_button.removeClass('col-new btn-outline-secondary d-none');
            close_button_ico.removeClass('bi-plus-square');
            close_button.addClass('col-close');
            close_button.addClass('btn-outline-warning');
            close_button_ico.addClass('bi-slash-square');

            /// Remove new element
            $('.elem-new').addClass('d-none');

            /// Disable other eddit buttons
            $('.row-edit').attr('disabled', 'disabled');
        }

        /// If action is to save - parse data and make ajax call to an api
        if (button_save_action) {
            editable_tds.removeClass('table-info');
            editable_inputs.attr('disabled', 'disabled');

            /// Parse select data - make an object from array of elements
            const request_data = {}
            editable_inputs.each((index, elem) => {
                const jquery_elem = $(elem);
                set_request_data_from_id(jquery_elem.attr('id'), jquery_elem.val(), request_data);
            });

            /// Make a save call and reload page
            apiCallAndReload({}, request_data, () => {
                /// Error - remove eddit classes fro, buttons
                button.removeClass('col-edit');
                button.removeClass('btn-outline-primary');
                button_icon.removeClass('bi-pencil-square');

                /// Error - place save button
                button.addClass('col-save');
                button.addClass('btn-outline-success');
                button_icon.addClass('bi-check2-square');

                /// Error - only close button
                editable_tds.addClass('table-danger');
                editable_inputs.removeAttr('disabled');
            });
        }
    });
});
