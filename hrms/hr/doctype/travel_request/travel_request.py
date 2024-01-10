# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from math import ceil
import frappe
from frappe.model.document import Document
from datetime import timedelta, datetime as dt
from frappe.utils import (
	get_datetime,
)

from hrms.hr.utils import validate_active_employee


class TravelRequest(Document):
	def validate(self):
		validate_active_employee(self.employee)

	def before_save(self):
		self.total_cost = sum([a.total_amount for a in self.costings ])


	@frappe.whitelist()
	def generate_costings(self):
		grade = self.employee_grade
		
		# frappe.msgprint(f"grade is {grade}")

		if grade:
		    # get table
			costs_region = frappe.db.sql(f"select * from `tabGrade Expense Item` where parent='{grade}'",as_dict=True)
			# frappe.msgprint(f"costs_region is {costs_region}")
			self.costings = [a for a in self.costings if a['expense_type'] not in ['Nuitée','Déjeuner','Dîner','Transport']]
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

				zone = self._get_zone(zone)
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

				if start.hour>18:
					num_diner -= 1
				if end.hour<18:
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
		while zone not in zones:
			zone = frappe.db.get_value('Territory',zone,'parent_territory')

		return zone