from dateutil.relativedelta import relativedelta

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_year_ending, get_year_start, getdate

from erpnext.setup.doctype.employee.test_employee import make_employee
from erpnext.setup.doctype.holiday_list.test_holiday_list import set_holiday_list

from hrms.hr.doctype.attendance.attendance import mark_attendance
from hrms.hr.doctype.leave_application.test_leave_application import make_allocation_record
from hrms.hr.report.monthly_attendance_sheet.monthly_attendance_sheet import execute
from hrms.payroll.doctype.salary_slip.test_salary_slip import (
	make_holiday_list,
	make_leave_application,
)
from hrms.tests.test_utils import get_first_day_for_prev_month

test_dependencies = ["Shift Type"]


class TestMonthlyAttendanceSheet(FrappeTestCase):
	def setUp(self):
		self.employee = make_employee("test_employee@example.com", company="_Test Company")
		frappe.db.delete("Attendance")

		date = getdate()
		from_date = get_year_start(date)
		to_date = get_year_ending(date)
		make_holiday_list(from_date=from_date, to_date=to_date)

	@set_holiday_list("Salary Slip Test Holiday List", "_Test Company")
	def test_monthly_attendance_sheet_report(self):
		previous_month_first = get_first_day_for_prev_month()

		company = frappe.db.get_value("Employee", self.employee, "company")

		# mark different attendance status on first 3 days of previous month
		mark_attendance(self.employee, previous_month_first, "Absent")
		mark_attendance(self.employee, previous_month_first + relativedelta(days=1), "Present")
		mark_attendance(self.employee, previous_month_first + relativedelta(days=2), "On Leave")

		filters = frappe._dict(
			{
				"month": previous_month_first.month,
				"year": previous_month_first.year,
				"company": company,
			}
		)
		report = execute(filters=filters)

		record = report[1][0]
		datasets = report[3]["data"]["datasets"]
		absent = datasets[0]["values"]
		present = datasets[1]["values"]
		leaves = datasets[2]["values"]

		# ensure correct attendance is reflected on the report
		self.assertEqual(self.employee, record.get("employee"))
		self.assertEqual(absent[0], 1)
		self.assertEqual(present[1], 1)
		self.assertEqual(leaves[2], 1)

	@set_holiday_list("Salary Slip Test Holiday List", "_Test Company")
	def test_detailed_view(self):
		previous_month_first = get_first_day_for_prev_month()
		company = frappe.db.get_value("Employee", self.employee, "company")

		# attendance with shift
		mark_attendance(self.employee, previous_month_first, "Absent", "Day Shift")
		mark_attendance(
			self.employee, previous_month_first + relativedelta(days=1), "Present", "Day Shift"
		)

		# attendance without shift
		mark_attendance(self.employee, previous_month_first + relativedelta(days=2), "On Leave")
		mark_attendance(self.employee, previous_month_first + relativedelta(days=3), "Present")

		filters = frappe._dict(
			{
				"month": previous_month_first.month,
				"year": previous_month_first.year,
				"company": company,
			}
		)
		report = execute(filters=filters)

		day_shift_row = report[1][0]
		row_without_shift = report[1][1]

		self.assertEqual(day_shift_row["shift"], "Day Shift")
		self.assertEqual(day_shift_row[1], "A")  # absent on the 1st day of the month
		self.assertEqual(day_shift_row[2], "P")  # present on the 2nd day

		self.assertEqual(row_without_shift["shift"], None)
		self.assertEqual(row_without_shift[4], "P")  # present on the 4th day

		# leave should be shown against every shift
		self.assertTrue(day_shift_row[3] == row_without_shift[3] == "L")

	@set_holiday_list("Salary Slip Test Holiday List", "_Test Company")
	def test_single_shift_with_leaves_in_detailed_view(self):
		previous_month_first = get_first_day_for_prev_month()
		company = frappe.db.get_value("Employee", self.employee, "company")

		# attendance with shift
		mark_attendance(self.employee, previous_month_first, "Absent", "Day Shift")
		mark_attendance(
			self.employee, previous_month_first + relativedelta(days=1), "Present", "Day Shift"
		)

		# attendance without shift
		mark_attendance(self.employee, previous_month_first + relativedelta(days=2), "On Leave")

		filters = frappe._dict(
			{
				"month": previous_month_first.month,
				"year": previous_month_first.year,
				"company": company,
			}
		)
		report = execute(filters=filters)
		# do not split for leave record
		self.assertEqual(len(report[1]), 1)

		day_shift_row = report[1][0]

		self.assertEqual(day_shift_row["shift"], "Day Shift")
		self.assertEqual(day_shift_row[1], "A")  # absent on the 1st day of the month
		self.assertEqual(day_shift_row[2], "P")  # present on the 2nd day
		self.assertEqual(day_shift_row[3], "L")  # leave on the 3rd day

	@set_holiday_list("Salary Slip Test Holiday List", "_Test Company")
	def test_summarized_view(self):
		previous_month_first = get_first_day_for_prev_month()
		company = frappe.db.get_value("Employee", self.employee, "company")

		# attendance with shift
		mark_attendance(self.employee, previous_month_first, "Absent", "Day Shift")
		mark_attendance(
			self.employee, previous_month_first + relativedelta(days=1), "Present", "Day Shift"
		)
		mark_attendance(
			self.employee, previous_month_first + relativedelta(days=2), "Half Day"
		)  # half day

		mark_attendance(
			self.employee, previous_month_first + relativedelta(days=3), "Present"
		)  # attendance without shift
		mark_attendance(
			self.employee, previous_month_first + relativedelta(days=4), "Present", late_entry=1
		)  # late entry
		mark_attendance(
			self.employee, previous_month_first + relativedelta(days=5), "Present", early_exit=1
		)  # early exit

		leave_application = get_leave_application(self.employee)

		filters = frappe._dict(
			{
				"month": previous_month_first.month,
				"year": previous_month_first.year,
				"company": company,
				"summarized_view": 1,
			}
		)
		report = execute(filters=filters)

		row = report[1][0]
		self.assertEqual(row["employee"], self.employee)

		# 4 present + half day absent 0.5
		self.assertEqual(row["total_present"], 4.5)
		# 1 present
		self.assertEqual(row["total_absent"], 1)
		# leave days + half day leave 0.5
		self.assertEqual(row["total_leaves"], leave_application.total_leave_days + 0.5)

		self.assertEqual(row["_test_leave_type"], leave_application.total_leave_days)
		self.assertEqual(row["total_late_entries"], 1)
		self.assertEqual(row["total_early_exits"], 1)

	@set_holiday_list("Salary Slip Test Holiday List", "_Test Company")
	def test_attendance_with_group_by_filter(self):
		previous_month_first = get_first_day_for_prev_month()
		company = frappe.db.get_value("Employee", self.employee, "company")

		# attendance with shift
		mark_attendance(self.employee, previous_month_first, "Absent", "Day Shift")
		mark_attendance(
			self.employee, previous_month_first + relativedelta(days=1), "Present", "Day Shift"
		)

		# attendance without shift
		mark_attendance(self.employee, previous_month_first + relativedelta(days=2), "On Leave")
		mark_attendance(self.employee, previous_month_first + relativedelta(days=3), "Present")

		filters = frappe._dict(
			{
				"month": previous_month_first.month,
				"year": previous_month_first.year,
				"company": company,
				"group_by": "Department",
			}
		)
		report = execute(filters=filters)

		department = frappe.db.get_value("Employee", self.employee, "department")
		department_row = report[1][0]
		self.assertIn(department, department_row["department"])

		day_shift_row = report[1][1]
		row_without_shift = report[1][2]

		self.assertEqual(day_shift_row["shift"], "Day Shift")
		self.assertEqual(day_shift_row[1], "A")  # absent on the 1st day of the month
		self.assertEqual(day_shift_row[2], "P")  # present on the 2nd day

		self.assertEqual(row_without_shift["shift"], None)
		self.assertEqual(row_without_shift[3], "L")  # on leave on the 3rd day
		self.assertEqual(row_without_shift[4], "P")  # present on the 4th day

	def test_attendance_with_employee_filter(self):
		previous_month_first = get_first_day_for_prev_month()

		company = frappe.db.get_value("Employee", self.employee, "company")
		employee2 = make_employee("test_employee2@example.com", company="_Test Company")
		employee3 = make_employee("test_employee3@example.com", company="_Test Company")

		# mark different attendance status on first 3 days of previous month for employee1
		mark_attendance(self.employee, previous_month_first, "Absent")
		mark_attendance(self.employee, previous_month_first + relativedelta(days=1), "Present")
		mark_attendance(self.employee, previous_month_first + relativedelta(days=2), "On Leave")

		# mark different attendance status on first 3 days of previous month for employee2
		mark_attendance(employee2, previous_month_first, "Absent")
		mark_attendance(employee2, previous_month_first + relativedelta(days=1), "Present")
		mark_attendance(employee2, previous_month_first + relativedelta(days=2), "On Leave")

		# mark different attendance status on first 3 days of previous month for employee3
		mark_attendance(employee3, previous_month_first, "Absent")
		mark_attendance(employee3, previous_month_first + relativedelta(days=1), "Present")
		mark_attendance(employee3, previous_month_first + relativedelta(days=2), "On Leave")

		filters = frappe._dict(
			{
				"month": previous_month_first.month,
				"year": previous_month_first.year,
				"company": company,
				"employee": self.employee,
			}
		)
		report = execute(filters=filters)

		record = report[1][0]
		datasets = report[3]["data"]["datasets"]
		absent = datasets[0]["values"]
		present = datasets[1]["values"]
		leaves = datasets[2]["values"]

		# ensure that only show the attendance for the specified employee
		self.assertEqual(len(report[1]), 1)

		# ensure correct attendance is reflected on the report
		self.assertEqual(self.employee, record.get("employee"))
		self.assertEqual(absent[0], 1)
		self.assertEqual(present[1], 1)
		self.assertEqual(leaves[2], 1)

	def test_attendance_with_employee_filter_and_summarized_view(self):
		previous_month_first = get_first_day_for_prev_month()

		company = frappe.db.get_value("Employee", self.employee, "company")
		employee2 = make_employee("test_employee2@example.com", company="_Test Company")
		employee3 = make_employee("test_employee3@example.com", company="_Test Company")

		# mark different attendance status on first 3 days of previous month for employee1
		mark_attendance(self.employee, previous_month_first, "Absent")
		mark_attendance(self.employee, previous_month_first + relativedelta(days=1), "Present")
		mark_attendance(self.employee, previous_month_first + relativedelta(days=2), "On Leave")

		# mark different attendance status on first 3 days of previous month for employee2
		mark_attendance(employee2, previous_month_first, "Absent")
		mark_attendance(employee2, previous_month_first + relativedelta(days=1), "Present")
		mark_attendance(employee2, previous_month_first + relativedelta(days=2), "On Leave")

		# mark different attendance status on first 3 days of previous month for employee3
		mark_attendance(employee3, previous_month_first, "Absent")
		mark_attendance(employee3, previous_month_first + relativedelta(days=1), "Present")
		mark_attendance(employee3, previous_month_first + relativedelta(days=2), "On Leave")

		filters = frappe._dict(
			{
				"month": previous_month_first.month,
				"year": previous_month_first.year,
				"company": company,
				"employee": self.employee,
				"summarized_view": 1,
			}
		)
		report = execute(filters=filters)

		record = report[1][0]
		datasets = report[3]["data"]["datasets"]
		absent = datasets[0]["values"]
		present = datasets[1]["values"]
		leaves = datasets[2]["values"]

		# ensure that only show the attendance for the specified employee
		self.assertEqual(len(report[1]), 1)

		# ensure correct attendance is reflected on the report
		self.assertEqual(self.employee, record.get("employee"))
		self.assertEqual(absent[0], 1)
		self.assertEqual(present[1], 1)
		self.assertEqual(leaves[2], 1)

	@set_holiday_list("Salary Slip Test Holiday List", "_Test Company")
	def test_validations(self):
		# validation error for filters without month and year
		self.assertRaises(frappe.ValidationError, execute_report_with_invalid_filters)

		# execute report without attendance record
		previous_month_first = get_first_day_for_prev_month()

		company = frappe.db.get_value("Employee", self.employee, "company")
		filters = frappe._dict(
			{
				"month": previous_month_first.month,
				"year": previous_month_first.year,
				"company": company,
				"group_by": "Department",
			}
		)
		report = execute(filters=filters)
		self.assertEqual(report, ([], [], None, None))


def get_leave_application(employee):
	previous_month_first = get_first_day_for_prev_month()

	year_start = getdate(get_year_start(previous_month_first))
	year_end = getdate(get_year_ending(previous_month_first))

	make_allocation_record(employee=employee, from_date=year_start, to_date=year_end)

	from_date = previous_month_first.replace(day=7)
	to_date = previous_month_first.replace(day=8)

	return make_leave_application(employee, from_date, to_date, "_Test Leave Type")


def execute_report_with_invalid_filters():
	filters = frappe._dict({"company": "_Test Company", "group_by": "Department"})
	execute(filters=filters)
