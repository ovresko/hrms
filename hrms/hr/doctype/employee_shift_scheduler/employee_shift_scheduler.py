# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe

class EmployeeShiftScheduler(Document):
	def validate(self):
		start = self.start_date
		end = self.end_date
		exists = frappe.db.sql(""" select name from `tabEmployee Shift Scheduler` where active=1 and name!="{name}" and ((start_date>="{start_date}" and start_date<="{end_date}") or (end_date>="{start_date}" and end_date<="{end_date}") or (end_date>="{end_date}" and start_date<="{start_date}")) """.format(name=self.name,start_date=self.start_date,end_date=self.end_date),as_dict=1)
		if exists:
			frappe.throw(f"Il existe un autre planifacteur {exists[0]['name']} sur la meme periode!")