import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.background_jobs import enqueue

class BulkLeaveApplication(Document):
    def on_submit(self):
        # Trigger background job on submit
        enqueue(
            method=create_bulk_leave_applications,
            queue='default',
            job_name=f"Create Leave Applications for {self.name}",
            bulk_leave=self.name,
            timeout=1500
        )

def create_bulk_leave_applications(bulk_leave):
    bulk_doc = frappe.get_doc("Bulk Leave Application", bulk_leave)
    
    # Check if 'employees' field is filled
    employee_names = []
    if bulk_doc.employees:
        # Split employee names from the text field
        employee_names = [name.strip() for name in bulk_doc.employees.split('\n') if name.strip()]
        # Fetch employee details only for listed employees
        employees = frappe.get_all("Employee", 
            filters={"status": "Active", "name": ["in", employee_names]},
            fields=["name", "employee_name"]
        )
    else:
        # Fetch all active employees
        employees = frappe.get_all("Employee", 
            filters={"status": "Active"},
            fields=["name", "employee_name"]
        )

    success, failed = [], []

    for employee in employees:
        try:
            # Create leave application
            leave_app = frappe.new_doc("Leave Application")
            leave_app.employee = employee.name
            leave_app.leave_type = bulk_doc.leave_type
            leave_app.from_date = bulk_doc.date_start
            leave_app.to_date = bulk_doc.date_fin
            leave_app.reason = bulk_doc.reason
            leave_app.status = "Approved"  # Auto-approve the leave application
            leave_app.save()
            leave_app.submit()

            # Track success
            success.append(employee.employee_name)
        except Exception as e:
            # Track failure with employee name and error
            failed.append(f"{employee.employee_name} - {str(e)}")

    # Update Bulk Leave Application with the results
    bulk_doc.db_set('success', '\n'.join(success))
    bulk_doc.db_set('failed', '\n'.join(failed))
    frappe.db.commit()
