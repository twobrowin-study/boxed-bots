
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

        /// Get all of table data cells witch are avaliable to eddit as text
        const editable_text_tds = row.children('.row-editable:not(:has(>select))');

        /// Get all of table data wuth selects witch are avalibale to choose
        const editable_select_tds = row.children('.row-editable:has(>select)');
        const editable_selects    = editable_select_tds.children('select');

        /// If action is to start an eddit - start an eddit
        if (button_edit_action) {
            editable_tds.addClass('table-info');
            editable_text_tds.attr('contenteditable', 'true');
            editable_selects.removeAttr('disabled');

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
            editable_text_tds.attr('contenteditable', 'false');
            editable_selects.attr('disabled', 'disabled');

            const request_data = {}

            /// Split element`s id and make it nested objects
            /// e.g. element with id settings-my_name-value and text 'value' would be
            /// {settings: {my_name: {value: 'value'}}}
            function set_request_data_from_id(id, set_value) {
                let curr_request_data = request_data
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

            /// Parse text data - make an object from array of elements
            editable_text_tds.each((index, elem) => {
                const jquery_elem = $(elem);
                const elem_divs = jquery_elem.children('div');

                /// Default variant - there is no div elements
                /// that are created via eddit mode
                var text = jquery_elem.text();

                /// There are div elements - parce them
                if (elem_divs.length > 0) {
                    text = jquery_elem.html()
                        .trim()
                        .replace(/<br(\s*)\/*>/ig, '\n')
                        .replace(/<[p|div]\s/ig,   '\n$0')
                        .replace(/([^>\s])<\/[p|div]+>/ig,'$1\n')
                        .replace(/(<([^>]+)>)/ig, '')
                        .trim();
                }

                set_request_data_from_id(jquery_elem.attr('id'), text);
            });

            /// Parse select data - make an object from array of elements
            editable_selects.each((index, elem) => {
                const jquery_elem = $(elem);
                set_request_data_from_id(jquery_elem.attr('id'), jquery_elem.val());
            });

            /// Make a save call and reload page
            $.ajax({
                url:  window.location.pathname,
                type: 'POST',
                data: JSON.stringify(request_data),
                contentType: 'application/json',
                headers: {
                    Accept: 'application/json'
                },
                success: () => location.reload(),
                error: () => {
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
                    editable_text_tds.attr('contenteditable', 'true');
                    editable_selects.removeAttr('disabled');

                    /// Error - show error
                    $('#there-was-en-error').removeClass('d-none');
                }
            });
        }
    });
});


/////////
/// Row append action
/////////
$(() => {
    $('.row-new, .row-close').click((elem) => {
        /// Check action - is it create new element or close update
        const button = $(elem.delegateTarget);
        const button_new_action   = button.hasClass('row-new');
        const button_close_action = button.hasClass('row-close');

        /// Close action - reload page
        if (button_close_action) {
            location.reload()
        }

        /// Toggle eddit and save statuses
        button.toggleClass('row-new row-close');
        button.toggleClass('btn-outline-secondary btn-outline-warning');
        button.children().toggleClass('bi-plus-square bi-slash-square');

        /// New lement - show it and disable eddit buttons
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

        /// Get all of table data cells witch are avaliable to eddit as text
        const editable_text_tds = $(`.${col_id}:not(:has(>select))`);

        /// Get all of table data wuth selects witch are avalibale to choose
        const editable_select_tds = $(`.${col_id}:has(>select)`);
        const editable_selects    = editable_select_tds.children('select');

        /// If action is to start an eddit - start an eddit
        if (button_edit_action) {
            editable_tds.addClass('table-info');
            editable_text_tds.attr('contenteditable', 'true');
            editable_selects.removeAttr('disabled');

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
            editable_text_tds.attr('contenteditable', 'false');
            editable_selects.attr('disabled', 'disabled');

            const request_data = {}

            /// Split element`s id and make it nested objects
            /// e.g. element with id settings-my_name-value and text 'value' would be
            /// {settings: {my_name: {value: 'value'}}}
            function set_request_data_from_id(id, set_value) {
                let curr_request_data = request_data
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

            /// Parse text data - make an object from array of elements
            editable_text_tds.each((index, elem) => {
                const jquery_elem = $(elem);
                const elem_divs = jquery_elem.children('div');

                /// Default variant - there is no div elements
                /// that are created via eddit mode
                var text = jquery_elem.text();

                /// There are div elements - parce them
                if (elem_divs.length > 0) {
                    text = jquery_elem.html()
                                                        .trim()
                                                        .replace(/<br(\s*)\/*>/ig, '\n')
                                                        .replace(/<[p|div]\s/ig,   '\n$0')
                                                        .replace(/([^>\s])<\/[p|div]+>/ig,'$1\n')
                                                        .replace(/(<([^>]+)>)/ig, '')
                                                        .trim();
                }

                set_request_data_from_id(jquery_elem.attr('id'), text);
            });

            /// Parse select data - make an object from array of elements
            editable_selects.each((index, elem) => {
                const jquery_elem = $(elem);
                set_request_data_from_id(jquery_elem.attr('id'), jquery_elem.val());
            });

            /// Make a save call and reload page
            $.ajax({
                url:  window.location.pathname,
                type: 'POST',
                data: JSON.stringify(request_data),
                contentType: 'application/json',
                headers: {
                    Accept: 'application/json'
                },
                success: () => location.reload(),
                error: () => {
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
                    editable_text_tds.attr('contenteditable', 'true');
                    editable_selects.removeAttr('disabled');

                    /// Error - show error
                    $('#there-was-en-error').removeClass('d-none');
                }
            });
        }
    });
});
