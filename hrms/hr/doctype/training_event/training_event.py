# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import time_diff_in_seconds
from frappe.utils import add_days, date_diff, get_datetime, getdate, format_date
from erpnext.setup.doctype.employee.employee import is_holiday

from erpnext.setup.doctype.employee.employee import get_employee_emails


class TrainingEvent(Document):
	def validate(self):
		self.set_employee_emails()
		self.validate_period()

	def on_submit(self):
		# Register attendance for remote work during the travel period
		self.register_attendance_for_remote_work()
  
	def on_update_after_submit(self):
		self.set_status_for_attendees()

	def set_employee_emails(self):
		self.employee_emails = ", ".join(get_employee_emails([d.employee for d in self.employees]))

	def validate_period(self):
		if time_diff_in_seconds(self.end_time, self.start_time) <= 0:
			frappe.throw(_("End time cannot be before start time"))

	def set_status_for_attendees(self):
		if self.event_status == "Completed":
			for employee in self.employees:
				if employee.attendance == "Present" and employee.status != "Feedback Submitted":
					employee.status = "Completed"

		elif self.event_status == "Scheduled":
			for employee in self.employees:
				employee.status = "Open"

		self.db_update_all()

	def register_attendance_for_remote_work(self):

		# Get the travel period based on the Itinerary's min departure_date and max return_date
		from_date = get_datetime(self.start_time)
		to_date =  get_datetime(self.end_time)

		event_days = date_diff(to_date, from_date) + 1
		for day in range(event_days):
			attendance_date = add_days(from_date, day)
			for employee in self.employees:
				if self.should_mark_attendance(attendance_date,employee.name):
					self.create_or_update_attendance(attendance_date,employee.name)

	def should_mark_attendance(self, attendance_date: str,employee: str) -> bool:
		# Check if attendance_date is a holiday
		if is_holiday(employee, attendance_date):
			return False

		# Check if employee is on leave
		if self.has_leave_record(attendance_date,employee):
			frappe.msgprint(
				_("Attendance not submitted for {0} as {1} is on leave.").format(
					frappe.bold(format_date(attendance_date)), frappe.bold(employee)
				)
			)
			return False

		return True

	def has_leave_record(self, attendance_date: str,employee) -> str | None:
		return frappe.db.exists(
			"Leave Application",
			{
				"employee": employee,
				"docstatus": 1,
				"from_date": ("<=", attendance_date),
				"to_date": (">=", attendance_date),
			},
		)

	def create_or_update_attendance(self, date: str,employee):
		attendance_name = self.get_attendance_record(date,employee)
		status = "Work From Home"  # Mark attendance as Remote Work

		if attendance_name:
			# update existing attendance, change the status
			doc = frappe.get_doc("Attendance", attendance_name)
			old_status = doc.status

			if old_status != status:
				doc.db_set({"status": status, "custom_training_event": self.name})
				text = _("changed the status from {0} to {1} via Training Event").format(
					frappe.bold(old_status), frappe.bold(status)
				)
				doc.add_comment(comment_type="Info", text=text)

				frappe.msgprint(
					_("Updated status from {0} to {1} for date {2} in the attendance record {3}").format(
						frappe.bold(old_status),
						frappe.bold(status),
						frappe.bold(format_date(date)),
						doc.name,
					),
					title=_("Attendance Updated"),
				)
		else:
			# submit a new attendance record
			doc = frappe.new_doc("Attendance")
			doc.employee = employee
			doc.attendance_date = date
			#doc.company = self.company
			doc.custom_training_event = self.name
			doc.status = status
			doc.insert(ignore_permissions=True)
			doc.submit()

	def get_attendance_record(self, attendance_date: str,employee) -> str | None:
		return frappe.db.exists(
			"Attendance",
			{
				"employee": employee,
				"attendance_date": getdate(attendance_date),
				"docstatus": ("!=", 2),
			},
		)