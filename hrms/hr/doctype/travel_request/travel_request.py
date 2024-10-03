# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from math import ceil
import frappe
from frappe import _
from frappe.model.document import Document
from datetime import timedelta, datetime as dt

from frappe.utils import add_days, date_diff, get_datetime, getdate, format_date
from hrms.hr.utils import validate_active_employee
from erpnext.setup.doctype.employee.employee import is_holiday

class TravelRequest(Document):
	def validate(self):
		validate_active_employee(self.employee)
		self.custom_leave_date = min([get_datetime(i.departure_date) for i in self.itinerary])
		self.custom_return_date = max([get_datetime(i.return_date) for i in self.itinerary])

	def before_save(self):
		self.total_cost = sum([a.total_amount for a in self.costings ])

	def on_submit(self):
		# Register attendance for remote work during the travel period
		self.register_attendance_for_remote_work()

	def register_attendance_for_remote_work(self):
		if not self.itinerary:
			frappe.throw(_("Itinerary is missing"))

		# Get the travel period based on the Itinerary's min departure_date and max return_date
		from_date = min([get_datetime(i.departure_date) for i in self.itinerary])
		to_date = max([get_datetime(i.return_date) for i in self.itinerary])

		travel_days = date_diff(to_date, from_date) + 1
		for day in range(travel_days):
			attendance_date = add_days(from_date, day)
			if self.should_mark_attendance(attendance_date):
				self.create_or_update_attendance(attendance_date)

	def should_mark_attendance(self, attendance_date: str) -> bool:
		# Check if attendance_date is a holiday
		if is_holiday(self.employee, attendance_date):
			frappe.msgprint(
				_("Attendance not submitted for {0} as it is a Holiday.").format(
					frappe.bold(format_date(attendance_date))
				)
			)
			return False

		# Check if employee is on leave
		if self.has_leave_record(attendance_date):
			frappe.msgprint(
				_("Attendance not submitted for {0} as {1} is on leave.").format(
					frappe.bold(format_date(attendance_date)), frappe.bold(self.employee)
				)
			)
			return False

		return True

	def has_leave_record(self, attendance_date: str) -> str | None:
		return frappe.db.exists(
			"Leave Application",
			{
				"employee": self.employee,
				"docstatus": 1,
				"from_date": ("<=", attendance_date),
				"to_date": (">=", attendance_date),
			},
		)

	def create_or_update_attendance(self, date: str):
		attendance_name = self.get_attendance_record(date)
		status = "Work From Home"  # Mark attendance as Remote Work

		if attendance_name:
			# update existing attendance, change the status
			doc = frappe.get_doc("Attendance", attendance_name)
			old_status = doc.status

			if old_status != status:
				doc.db_set({"status": status, "travel_request": self.name})
				text = _("changed the status from {0} to {1} via Travel Request").format(
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
			doc.employee = self.employee
			doc.attendance_date = date
			#doc.company = self.company
			doc.travel_request = self.name
			doc.status = status
			doc.insert(ignore_permissions=True)
			doc.submit()

	def get_attendance_record(self, attendance_date: str) -> str | None:
		return frappe.db.exists(
			"Attendance",
			{
				"employee": self.employee,
				"attendance_date": attendance_date,
				"docstatus": ("!=", 2),
			},
		)


	@frappe.whitelist()
	def generate_costings(self):
		grade = self.employee_grade
		
		# frappe.msgprint(f"grade is {grade}")

		if grade:
			self.custom_leave_date = min([get_datetime(i.departure_date) for i in self.itinerary])
			self.custom_return_date = max([get_datetime(i.return_date) for i in self.itinerary])
		    # get table
			costs_region = frappe.db.sql(f"select * from `tabGrade Expense Item` where parent='{grade}'",as_dict=True)
			# frappe.msgprint(f"costs_region is {costs_region}")
			self.costings = [a for a in self.costings if a.expense_type not in ['Nuitée','Déjeuner','Dîner','Transport']]
			#expense_types = [q.expense_type for q in self.costings]
			# self.costings = [a for a in self.costings if "jours:" not in (a.comments or "")]

			for iter in self.itinerary:
				zone = iter.zone
				start = get_datetime(iter.departure_date)
				end = get_datetime(iter.return_date)
				_start =start.replace(hour=0)
				_end = end.replace(hour=0)
				 
				days = ceil(((_end - _start).total_seconds() / 60 / 60) / 24) + 1 
				if end.day == start.day and end.month == start.month:
					days = 0

				res = self._get_zone(zone)
				zone = res[0]
				distance = res[1]
				iter.parent_zone = zone
				price_nuite = [c for c in costs_region if c['expense_claim_type'] == "Nuitée" and c['territory'] == zone and not c.get('fixed') and not c.get('euro')]
				price_nuite = price_nuite[0]['amount'] if price_nuite else 0
    
				price_dijeuner = [c for c in costs_region if c['expense_claim_type'] == "Déjeuner" and c['territory'] == zone and not c.get('fixed') and not c.get('euro')]
				price_dijeuner = price_dijeuner[0]['amount'] if price_dijeuner else 0
    
				price_diner = [c for c in costs_region if c['expense_claim_type'] == "Dîner" and c['territory'] == zone and not c.get('fixed') and not c.get('euro')]
				price_diner = price_diner[0]['amount'] if price_diner else 0

				num_dijeuner = days  if days else 1
				num_diner = days  if days else 1
				num_nuite = days if zone == "Reste du monde" else days-1

				
				if start.hour>12 :
					num_dijeuner -= 1
				if end.hour<12 :
					num_dijeuner -= 1

				if start.hour>20:
					num_diner -= 1
				if end.hour<20:
					num_diner -= 1

				if num_diner<0:
					num_diner=0
				if num_dijeuner<0:
					num_dijeuner=0
				if num_nuite<0:
					num_nuite=0

				dijeuner = num_dijeuner*price_dijeuner
				nuite = num_nuite	*	price_nuite
				diner = num_diner * price_diner

				if distance and distance>0:
					carburant = 2 * distance * 5 # 2 * km * 5da
					#bons = (carburant // 850 )+1
					self.append('costings',{
						'expense_type':"Frais de carburant",
						'funded_amount':carburant,
						'total_amount':carburant,
						'comments': f"{distance*2}Km x 5DA"
					})
				
				if dijeuner:
					self.append('costings',{
						'expense_type':"Déjeuner",
						'funded_amount':dijeuner,
						'total_amount':dijeuner,
						'comments': f"{price_dijeuner}DA x {num_dijeuner} jours"
					})

				if diner:
					self.append('costings',{
						'expense_type':"Dîner",
						'total_amount':diner,
						'funded_amount':diner,
						'comments': f"{price_diner}DA x {num_diner} jours"
					})

				if nuite:
					self.append('costings',{
						'expense_type':"Nuitée",
						'total_amount':nuite,
						'funded_amount':nuite,
						'comments': f"{price_nuite}DA x {num_nuite} jours"
					})


				if zone == "Reste du monde":
					# add transport
					price_trans_ = [c for c in costs_region if c['expense_claim_type'] == "Transport" and c['territory'] == zone]
					price_trans = price_trans_[0]['amount'] if price_trans_ else 0
					tranport = price_trans
					if price_trans_ and not price_trans_[0]['fixed']:
						tranport = price_trans * days
					if tranport:
						self.append('costings',{
							'expense_type':"Transport",
							'total_amount':tranport,
							'funded_amount':tranport,
							'comments': f"{price_trans}DA x {days} jours"
						})
      
				# FIXED
				price_nuite = [c for c in costs_region if c['expense_claim_type'] == "Nuitée" and c['territory'] == zone and c.get('euro')]
				price_nuite = price_nuite[0]['amount'] if price_nuite else 0
    
				if price_nuite:
					self.append('costings',{
						'expense_type':"Nuitée",
						'custom_total_devise':price_nuite* days,
						'comments': f"{price_nuite}DA"
					})

				a=dt.now()  
				
			self.total_cost = sum([a.total_amount or 0 for a in self.costings ])
			# frappe.msgprint(f"costings is {self.costings}")

    

	def _get_zone(self,zone):
		zones = ["Sud","Est","Centre","Ouest","Reste du monde"]
		distance = 0
		while zone not in zones:
			if not distance:
				distance = frappe.db.get_value('Territory',zone,'custom_distance')
			zone = frappe.db.get_value('Territory',zone,'parent_territory')

		return [zone,distance]