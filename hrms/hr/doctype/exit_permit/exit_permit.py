import frappe
from frappe import _
from frappe.utils import getdate, nowdate, add_months
from frappe.model.document import Document

class Exitpermit(Document):
    def before_insert(self):
        # Get today's date
        today = getdate(nowdate())
        employee = self.employee
        if self.type_exit=="Sortie":

            # Retrieve settings from HR Settings
            hr_settings = frappe.get_single("HR Settings")
            max_exit_permit_count = hr_settings.max_exit_permit_count or 2  # Default to 2 permits if not set
            max_exit_permit_hours = hr_settings.max_exit_permit_hours or 8  # Default to 8 hours if not set

            # Determine the start and end dates based on the 21st rule
            if today.day >= 21:
                # Start date is 21st of the current month, end date is 21st of the next month
                start_date = today.replace(day=21)
                end_date = add_months(start_date, 1)
            else:
                # Start date is 21st of the previous month, end date is 21st of the current month
                end_date = today.replace(day=21)
                start_date = add_months(end_date, -1)

            # Step 1: Get exit permits for the employee in the current 21-to-21 day period
            permits = frappe.get_all('Exit permit', filters={
                'employee': employee,
                'type_exit':"Sortie",
                'exit_date': ['between', [start_date, end_date]]
            })
            count = len(permits)+1

            # Step 2: If the employee has fewer than max_exit_permit_count permits, calculate the total requested time in hours
            if count < max_exit_permit_count:
                total_requested_time = self.duration / 3600 if self.duration else 0

                # Step 3: Loop through the permits to sum up durations (convert seconds to hours)
                for permit in permits:
                    permit_doc = frappe.get_doc('Exit permit', permit['name'])
                    total_requested_time += (permit_doc.duration / 3600) if permit_doc.duration else 0
                

                # Step 5: Ensure the total requested time does not exceed the limit from HR Settings
                if total_requested_time > max_exit_permit_hours:
                    frappe.throw(_("Le temps total demandé {0} heures dépasse la limite de {1} heures.".format(total_requested_time,max_exit_permit_hours)))
            else:
                frappe.throw(_("Vous ne pouvez pas créer plus de {0} permis de sortie pour la période actuelle de 21 jours.".format(max_exit_permit_count)))
