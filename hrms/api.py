import logging
import frappe
import json
import datetime
from dateutil import parser
from frappe.utils import cint
from frappe import _
from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee,is_holiday



@frappe.whitelist()
def assign_shift_assignment(*args,**kwargs):
    shift_type = kwargs['shift_type']
    start = kwargs['start']
    end = kwargs['end']
    
    frappe.msgprint('Terminee')
    frappe.msgprint(start)
    frappe.msgprint(end)
    
@frappe.whitelist()
def vacance_all(*args,**kwargs):
    #if kwargs:
    doc = json.loads(kwargs['doc'])
    frappe.db.sql("""update `tabEmployee` set holiday_list='%s' where status='Active'""" % doc.get('name'))
    frappe.db.sql("""update `tabShift Type` set holiday_list='%s' where 1=1""" % doc.get('name'))
    frappe.msgprint('Terminee')

@frappe.whitelist()
def assign_all(*args,**kwargs):
    #if kwargs:
    doc = json.loads(kwargs['doc'])    
    frappe.db.sql("""update `tabEmployee` set default_shift='%s' where status='Active'""" % doc.get('name'))
    frappe.msgprint('Terminee')
    #frappe.msgprint(doc)
    #frappe.msgprint(args)
    #frappe.msgprint(str(type(args)))

@frappe.whitelist()
def process_shift_scheduler(*args,**kwargs):
    print('processing scheduler...')
    _today = datetime.datetime.today()
    _now = datetime.datetime.now()
    _yesterday = datetime.datetime.today() - datetime.timedelta(days=1)
    _yesterday = _yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    _today_nidnight = _today.replace(hour=0, minute=0, second=0, microsecond=0)
    _td = _today.weekday()
    hour = _today.hour
    schedules = frappe.get_all(
        "Employee Shift Scheduler",
        fields=[
            "name",
            "holiday",
            "start_date",
            "end_date"
        ],
        filters=[
            ["active",'=', 1],
            ["start_date", "<=", _yesterday],
            ["end_date", ">=", _yesterday]
        ],
    )
    if not schedules:
        print(f"No schedules on {_yesterday}")
        return
    if len(schedules)>1:
        print(f"More then 1 schedules ({len(schedules)}) on {_yesterday}")

    for schedule in schedules:
        schedulers = frappe.db.sql("""select * from `tabEmployee Shift Scheduler Item`  where parent='{schedule}' order by idx""".format(schedule=schedule['name']), as_dict=1)
        print(f'day {_td} | hour {hour}')
        days = {
            0:'Lundi',
            1:'Mardi',
            2:'Mercredi',
            3:'Jeudi',
            4:'Vendredi',
            5:'Samedi',
            6:'Dimanche',
        }
        td = days[_td]
        pd = None
        if _td>0:
            pd = days[_td-1]
        else:
            pd = days[6]

        employees = [a['employee'] for a in schedulers]
        # frappe.db.sql("""update `tabEmployee` set equipe_de_permanence=0 where equipe_de_permanence=1 """)
        # frappe.db.commit()
        frappe.db.sql("""update `tabEmployee` set default_shift='', equipe_de_permanence=1 where name in ({emps})""".format(emps=','.join([f"'{w}'" for w in employees])))
        frappe.db.commit()
        # yesterday program
        schedulers = [a for a in schedulers if a['day_of_week']==pd]
        print(f"employees working {pd}, processing {len(schedulers)} schedulers...")
        print(employees)

        for scheduler in schedulers:
            try:            
                employee = scheduler.get('employee')
                activeEmp = frappe.db.get_value("Employee",employee, "status")
                if activeEmp != "Active":
                    print("EMPLOYEE NOT ACTIVE")
                    continue
                print('===========================')
                print(employee)

                holiday_list_name = schedule.get('holiday') or get_holiday_list_for_employee(employee,False)
                print(f"holiday_list_name {holiday_list_name}")
                if holiday_list_name:
                    filters = {"parent": holiday_list_name, "holiday_date": _yesterday}
                    filters["weekly_off"] = False
                    holidays = frappe.get_all("Holiday", fields=["description"], filters=filters, pluck="description")
                    if len(holidays) > 0:
                        print(f"holiday on {_yesterday} {holiday_list_name} ")
                        continue
                shift_type = scheduler.get('shift_type')
                if not shift_type:
                    print(f"No shift, skipping")
                    continue
                shift_doc = frappe.get_doc('Shift Type',shift_type)
                if (
                    not cint(shift_doc.enable_auto_attendance)
                    or not shift_doc.process_attendance_after
                    or not shift_doc.last_sync_of_checkin
                ):
                    print(f"Cannot mark for now, skipping")
                    continue

                grace = shift_doc.get('begin_check_in_before_shift_start_time') or 0
                end_time = shift_doc.get('end_time')
                start_time = shift_doc.get('start_time')
                print(f"shift start_time : {start_time}/{end_time}")

                yesterday_start = _yesterday  + start_time
                presence = frappe.db.exists(
                    "Attendance",
                    {
                        "employee": employee,
                        "docstatus":1,
                        "attendance_date": _yesterday.date(),
                    },
                )
                if presence:
                    print("Attendance already marked!")
                    continue
                yesterday_end = _yesterday+ end_time
                attendance_date = yesterday_start.date()
                print(f"start {yesterday_start}/{yesterday_end}")
                if end_time<start_time:
                    print(f"2day shift")

                    yesterday_end = _today_nidnight+ end_time
                    if yesterday_end >= _now-datetime.timedelta(hours=4):
                        print(f"not time to mark yet, end shift: {end_time} now+grace is {_now}")
                        continue
                    log_names,attendance_status , total_working_hours, late_entry, early_exit, in_time, out_time = get_employee_checkins(shift_doc,employee,yesterday_start,yesterday_end)
                    print(f"attendance_status",attendance_status)
                    print(f"total_working_hours",total_working_hours)
                    print(f"late_entry",late_entry)
                    print(f"early_exit",early_exit)
                    print(f"in_time",in_time)
                    print(f"out_time",out_time)
                    mark_presence(log_names,employee,attendance_date,attendance_status,total_working_hours,shift_doc.name,late_entry,early_exit,in_time,out_time,scheduler.get('name'))
                else:
                    log_names,attendance_status , total_working_hours, late_entry, early_exit, in_time, out_time = get_employee_checkins(shift_doc,employee,yesterday_start,yesterday_end)
                    print(f"attendance_status",attendance_status)
                    print(f"total_working_hours",total_working_hours)
                    print(f"late_entry",late_entry)
                    print(f"early_exit",early_exit)
                    print(f"in_time",in_time)
                    print(f"out_time",out_time)
                    mark_presence(log_names,employee,attendance_date,attendance_status,total_working_hours,shift_doc.name,late_entry,early_exit,in_time,out_time,scheduler.get('name'))

            except Exception as e:
                logging.exception(e)

def get_employee_checkins(shift_doc,employee,start,finish):
    check_start = start-datetime.timedelta(hours=2)
    check_finish = finish+datetime.timedelta(hours=2)
    print(f"check start finish {employee}: {check_start}/{check_finish}")
    logs = frappe.get_all(
        "Employee Checkin",
        fields=[
            "name",
            "employee",
            "time",
        ],
        filters=[
            ["skip_auto_attendance",'=', 0],
            ["attendance","is", "not set"],            
            ["time", ">=", check_start],
            ["time", "<=", check_finish],
            ["employee",'=', str(employee)]
        ],
        order_by="time",
    )
    if not logs:
        return [],"Absent", 0, False, False, None, None

    log_names = [a['name'] for a in logs]
    late_entry = early_exit = False
    in_time = logs[0].time
    if len(logs) >= 2:
        out_time = logs[-1].time
    else:
        out_time = in_time
    print(f"logs: {len(logs)} |  in/out {in_time}/{out_time}")
    total_working_hours = time_diff_in_hours(in_time, out_time)

    if (
        in_time
        and in_time > start + shift_doc.start_time + datetime.timedelta(minutes=cint(shift_doc.late_entry_grace_period))
    ):
        late_entry = True

    if (
        out_time
        and out_time < finish - shift_doc.end_time - datetime.timedelta(minutes=cint(shift_doc.early_exit_grace_period))
    ):
        early_exit = True
    if (
        shift_doc.working_hours_threshold_for_absent
        and total_working_hours < shift_doc.working_hours_threshold_for_absent
    ):
        return log_names,"Absent", total_working_hours, late_entry, early_exit, in_time, out_time

    if (
        shift_doc.working_hours_threshold_for_half_day
        and total_working_hours < shift_doc.working_hours_threshold_for_half_day
    ):
        return log_names,"Half Day", total_working_hours, late_entry, early_exit, in_time, out_time

    return log_names,"Present", total_working_hours, late_entry, early_exit, in_time, out_time

def time_diff_in_hours(time1, time2):
    # if time2.day != time1.day:
    #     # Create datetime objects for the start and end times on the same day
    #     start_datetime = datetime.datetime(2000, 1, 1, time1.hour, time1.minute, time1.second)
    #     end_datetime = datetime.datetime(2000, 1, 2, time2.hour, time2.minute, time2.second)
    # else:
    #     # Create datetime objects for the start and end times on the same day
    #     start_datetime = datetime.datetime(2000, 1, 1, time1.hour, time1.minute, time1.second)
    #     end_datetime = datetime.datetime(2000, 1, 1, time2.hour, time2.minute, time2.second)

    # Calculate the time difference
    time_difference = time2 - time1
    #print(f"time_difference {time_difference} ** {start_datetime} {end_datetime}")
    # Convert the time difference to total hours
    total_hours = time_difference.total_seconds() / 3600
    return round(total_hours, 2)

def mark_presence(log_names,employee,attendance_date,attendance_status,working_hours,shift,late_entry,early_exit,in_time,out_time,scheduler):
    attendance = frappe.new_doc("Attendance")
    attendance.update(
        {
            "doctype": "Attendance",
            "employee": employee,
            "attendance_date": attendance_date,
            "status": attendance_status,
            "working_hours": working_hours,
            "shift": shift,
            "late_entry": late_entry,
            "early_exit": early_exit,
            "in_time": in_time,
            "out_time": out_time,
            "custom_planifier":True
        }
    ).submit()

    if attendance_status == "Absent":
        attendance.add_comment(
            text=f"Marquer absent depuis le planificateur de quart {scheduler}"
        )

    if log_names:
        EmployeeCheckin = frappe.qb.DocType("Employee Checkin")
        (
            frappe.qb.update(EmployeeCheckin)
            .set("attendance", attendance.name)
            .where(EmployeeCheckin.name.isin(log_names))
        ).run()
    #return attendance