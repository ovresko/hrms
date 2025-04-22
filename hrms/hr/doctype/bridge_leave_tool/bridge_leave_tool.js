
frappe.ui.form.on('Bridge leave tool', {
	refresh(frm) {
		frm.trigger("set_primary_action");
	},

	
	status(frm) {
		frm.trigger("set_primary_action");
	},

	reset_attendance_fields(frm) {
		frm.set_value("status", "");
		frm.set_value("shift", "");
		frm.set_value("late_entry", 0);
		frm.set_value("early_exit", 0);
	},



	set_primary_action(frm) {
		frm.disable_save();
		frm.page.set_primary_action(__("Mark Leave"), () => {

			frm.trigger("mark_leave");
		});
	},

	mark_leave(frm) {

		frappe
			.call({
				method: "hrms.hr.doctype.bridge_leave_tool.bridge_leave_tool.mark_employee_leave",
				args: {
					start_date: frm.doc.start_date,
					end_date: frm.doc.end_date,
					leave_type: frm.doc.leave_type,
					reason: frm.doc.reason,
				},
				freeze: true,
				freeze_message: __("Marking Leaves"),
			})
			.then((r) => {
				if (!r.exc) {
					frappe.show_alert({
						message: __("Leaves marked successfully"),
						indicator: "green",
					});
					frm.refresh();
				}
			});
	},
});
