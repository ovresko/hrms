# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import datetime
import json

import frappe
from frappe.model.document import Document
from frappe.utils import getdate

class Bridgeleavetool(Document):
	pass


@frappe.whitelist()
def mark_employee_leave(
	start_date: str | datetime.date,
	end_date: str | datetime.date,
	leave_type: str | None = None,
	reason: str | None = None,
) -> None:
	if isinstance(start_date, str):
		start_date = getdate(start_date)
	if isinstance(end_date, str):
		end_date = getdate(end_date)

	if not isinstance(start_date, datetime.date) or not isinstance(end_date, datetime.date):
		frappe.throw("Invalid date format for start_date or end_date.")

	if start_date > end_date:
		frappe.throw("Start date cannot be after end date.")

	if not leave_type:
		frappe.throw("Leave type must be specified.")

	if not reason:
		frappe.throw("Reason for leave must be specified.")

	employee_list = frappe.get_list(
		"Employee", fields=["employee", "employee_name"], filters={"status": "Active","name":"999999"}, order_by="employee_name"
	)
	for employee in employee_list:
		attendance = frappe.get_doc(
			dict(
				doctype="Leave Application",
				employee=employee,
				from_date=start_date,
				to_date=end_date,
				leave_type=leave_type,
				reason=reason,
				status="Approved",
			)
		)
		attendance.insert()
		attendance.submit()
