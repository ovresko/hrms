// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Shift Type', {
	refresh: function (frm) {
		frm.add_custom_button(
			__('Mark Attendance'),
			() => {
				if (!frm.doc.enable_auto_attendance) {
					frm.scroll_to_field('enable_auto_attendance');
					frappe.throw(__('Please Enable Auto Attendance and complete the setup first.'));
				}

				if (!frm.doc.process_attendance_after) {
					frm.scroll_to_field('process_attendance_after');
					frappe.throw(__('Please set {0}.', [__('Process Attendance After').bold()]));
				}

				if (!frm.doc.last_sync_of_checkin) {
					frm.scroll_to_field('last_sync_of_checkin');
					frappe.throw(__('Please set {0}.', [__('Last Sync of Checkin').bold()]));
				}

				frm.call({
					doc: frm.doc,
					method: 'process_auto_attendance',
					freeze: true,
					callback: () => {
						frappe.msgprint(__('Attendance has been marked as per employee check-ins'));
					}
				});
			}
		);

		frm.add_custom_button(
			__("Apply Shift Assignment"),
			() => {
				var me = this;
				var fields = [
					{ fieldtype: "Date", fieldname: "start", label: __("From Date"),reqd: 1 },
					{ fieldtype: "Date", fieldname: "end", label: __("To Date"),reqd: 1 }
				]

				const dialog  = new frappe.ui.Dialog({
					title: __("Apply Shift Assignment"),
					fields: fields,
					primary_action: function () {
						// var data =dialog.get_values();
						// frappe.msgprint(
						// 	dialog.fields_dict.start.value
						// );
						// return
						frm.call("assign_shift_assignment",{
								start: dialog.fields_dict.start.value,
								end: dialog.fields_dict.end.value,
							},
							(r) => {
								frappe.msgprint(
									r.message
								);
								d.hide();
								me.frm.reload_doc();
							},
						);
					},
					primary_action_label: __("Create"),
				});
				dialog.show();

			})

	}
});
