import logging
import frappe
import json
import datetime
from dateutil import parser
from frappe.utils import cint
from frappe import _
from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee,is_holiday
from datetime import datetime as dt
from frappe.utils.nestedset import rebuild_tree

from datetime import timedelta as td
from frappe.desk.doctype.notification_log.notification_log import (
	enqueue_create_notification,
	get_title,
	get_title_html,
)

def tc_inser(check):
    try:
        check.insert()
    except Exception as e:
        logging.info(e)
        
        
@frappe.whitelist()
def process_tasks(*args,**kwargs):
    # delay
    # send_notif("ovresko@gmail.com","test message","email content")
    today = dt.today().date()
    emptyProjects = frappe.db.sql(""" SELECT p.* ,COUNT(t.name) AS task_count FROM tabProject p LEFT JOIN tabTask t ON p.name = t.project  where p.status="Open" GROUP BY p.name; """,as_dict=True)
    if emptyProjects:
        for em in emptyProjects:
            creation = em.expected_start_date
            if creation and today>(creation+td(days=6)):
                assigned = frappe.get_all(
                    "ToDo",
                    fields=["name", "allocated_to", "description", "status"],
                    filters={
                        "reference_type": "Project",
                        "reference_name": em.name,
                        "status": ("not in", ("Cancelled", "Closed")),
                        "allocated_to": ("is", "set"),
                    },
                )
                #em.owner
                assignedUsers = [a['allocated_to'] for a in assigned]
                projUsers = [a['user'] for a in (em.users or [])]
                users = list(set(projUsers+assignedUsers+[em.owner]))  
                for u in users:
                    # send_notif(u,subject,msg)
                    check = frappe.get_doc({
                        'doctype': 'Task Check',
                        "type": "empty_project",
                        "reference_type":"Project",
                        "task":em.name,
                        "user":u
                    })
                    tc_inser(check)




    tasks = frappe.db.get_list("Task", {"status":["not in",["Completed","Cancelled"]]},["*"],  page_length=99999)
    for task in tasks:
        print(task.name)
        assigned = frappe.get_all(
            "ToDo",
            fields=["name", "allocated_to", "description", "status"],
            filters={
                "reference_type": "Task",
                "reference_name": task.name,
                "status": ("not in", ("Cancelled", "Closed")),
                "allocated_to": ("is", "set"),
            },
        )
        
        assigned = list(set([a.allocated_to for a in assigned]))
        for assign in assigned:
            try:
                process_task(assign,task)
            except Exception as e:
                logging.exception(e)

def process_task(userid,task):
    today = dt.today().date()
    print(type(task.exp_start_date))
    employee = frappe.get_doc("Employee",{"user_id":userid})
    superior1 = employee.reports_to
    superior2 = frappe.db.get_value('Employee', employee.name, 'reports_to')
    print(employee)
    print(superior1)
    print(superior2)

    # half_period
    # empty_project
    # 2_days_before
    # delay
    # new_task
    
    # 'doctype': 'Task Check',
    # "type": "empty_project",
    # "reference_type":"Project",
    # "task":em.name,
    # "user":u

    # half_period  
    allusers = [userid]
    if superior1:
        allusers.append(superior1)
    if superior2:
        allusers.append(superior2)
        
   
    if task.exp_end_date and task.exp_start_date and task.progress<50:
        period = (task.exp_end_date - task.exp_start_date).days
        if period>3:
            half = task.exp_start_date + td(days=int(period/2))
            if today>=half:
                for u in allusers:
                    check = frappe.get_doc({
                        'doctype': 'Task Check',
                        "reference_type":"Task",
                        "type": "half_period",
                        "task":task.name,
                        "user":u
                    })
                    tc_inser(check)


    # 2_days_before
    if   task.exp_end_date :
        deadline = task.exp_end_date - td(days=2)
        if deadline<=today:
            for u in allusers:
                check = frappe.get_doc({
                    'doctype': 'Task Check',
                    "reference_type":"Task",
                    "type": "2_days_before",
                    "task":task.name,
                    "user":u
                })
                tc_inser(check)
            

    # delay
    if task.modified and task.status=="Open" and task.priority!="Low" :
        
        delayed = (dt.today() - task.modified ).days
        if delayed > 6:
           for u in allusers:
                check = frappe.get_doc({
                    'doctype': 'Task Check',
                    "reference_type":"Task",
                    "type": "delay",
                    "task":task.name,
                    "user":u
                })
                tc_inser(check)
           

    
    # new_task
#     new_task = frappe.db.exists("Task Check", {"type": "new_task","task":task.name,"user":userid})
#     if not new_task and task.modified and task.status=="Open" and task.priority!="Low" :
        
#         delayed = (dt.today() - task.modified ).days
#         if delayed > 6:
#             subject = f"L'évolution de tache {task.name}"
#             msg=f"""
#     <p>Bonjour,</p>
#     <p>Pourriez-vous nous tenir informés de l'avancement de votre tâche, s'il vous plaît ? <br> 
#     Tâche: {task.name} / {task.subject}<br> 
#     Project <strong>{task.project}</strong> <br> 
#     Assignée à <strong>{userid}</strong><br> 
 
#     <p>Merci de votre attention et de votre collaboration.</p>
#     <p>Cordialement,<br>
# """
#             send_notif(userid,subject,msg)
#             if superior1:
#                 send_notif(superior1,subject,msg)
#             if superior2:
#                 send_notif(superior2,subject,msg)
#             check = frappe.get_doc({
#                 'doctype': 'Task Check',
#                 "type": "delay",
#                 "task":task.name,
#                 "user":userid
#             })
#             check.insert()

def send_notif(userid,subject,email_content):
    print("sending notif")
    frappe.sendmail(recipients=[userid], subject=subject, message=email_content)

@frappe.whitelist()
def reorder_tasks(doc, status):
    if doc.custom_index:
        exists = max = frappe.db.sql("select name from `tabTask` where custom_index=%(custom_index)s and project=%(project)s and name!=%(name)s",{"custom_index":doc.custom_index,"project":doc.project,"name":doc.name},as_dict=1)
        if exists:
            #exist = exists[0]
            frappe.db.sql("update `tabTask` set custom_index=IFNULL(custom_index,0)+1 where  custom_index>=%(custom_index)s and project=%(project)s and name!=%(name)s",{"custom_index":doc.custom_index,"project":doc.project,"name":doc.name},as_dict=1)

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

@frappe.whitelist()
def process_temp_reports(*args,**kwargs):
    today = datetime.datetime.today()
    reports = frappe.get_all(
        "Temp Report",
        fields=["name"],
        filters=[
            ["active",'=', 1],
            ["executed",'=', 0],
            ["from", "<=", today]
        ],
        order_by='`from` asc'
    )
    logging.warn(f"found {len(reports)} reports")
    for _report in reports:
        try:
            report = frappe.get_doc("Temp Report",_report.name)
            original_supervisor = report.original_supervisor
            replace_supervisor = report.replace_supervisor
            change_assignment = report.change_assignment
            logging.warn(f"handeling report {report.name}")
            
            if report.employees == None:
                report.employees=""
            employees = []
            if not report.employees and not report.linked:
                employees = frappe.get_all(
                    "Employee",
                    fields=["name","reports_to","employee_name"],
                    filters=[
                        ["reports_to",'=', original_supervisor],
                        ["status","=","Active"]
                    ],
                )
            elif report.employees :
                for emp in report.employees.splitlines():
                    if emp:
                        logging.warn(f"fetch link emp {emp}")
                        employees.append(frappe.get_doc("Employee",emp))
                
            logging.warn(f"employees {len(employees)}")
            
            affected = []
            
            for employee in employees:
                try:
                    logging.warn(f"updating {employee.employee_name}")
                    if report.linked:
                        linked_original_emp = frappe.db.get_value("Temp Report",report.linked,"replace_supervisor")
                        #reports_to = frappe.db.get_value("Employee",employee.name,"reports_to")
                        if employee.reports_to and employee.reports_to != linked_original_emp:
                            logging.warn(f"default report manualy to changed {report.name}")
                            continue
                            
                    if replace_supervisor == employee.name:
                        #reports_to = frappe.db.get_value("Employee",employee.name,"reports_to")
                        logging.warn(f"replace supervisor is same as employee {report.name}")
                    else:
                        frappe.db.set_value("Employee",employee.name,"reports_to",replace_supervisor)
                        affected.append(employee.name)
                        
                    if change_assignment:
                        logging.warn(f"changing assignmenets for {employee.employee_name}")
                        #
                except Exception as e:
                    logging.exception(e)
            report.employees = "\n".join(affected)
            report.executed = 1
            report.save(ignore_permissions=True)
            frappe.db.commit()
                    
            rebuild_tree("Employee")
           
            
            # frappe.db.set_value("Temp Report",report.name,"employees",affected)
            # frappe.db.set_value("Temp Report",report.name,"executed",1)
            
            if report.to and affected:
                logging.warn(f"setting end report to {report.to}")    
                frappe.get_doc({
                    "doctype":"Temp Report",
                    "from":report.to,
                    "original_supervisor":replace_supervisor,
                    "replace_supervisor":original_supervisor,
                    "change_assignment":change_assignment,
                    "active":1,
                    "executed":0,
                    "employees":"\n".join(affected),
                    "linked":report.name
                }).insert(ignore_permissions=True)
                
        except Exception as e:
            logging.exception(e)