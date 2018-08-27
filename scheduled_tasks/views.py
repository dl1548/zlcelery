# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render,HttpResponse,render_to_response

from scheduled_tasks import tasks

# Create your views here.
from djcelery.models import PeriodicTask, CrontabSchedule
from djcelery.schedulers import ModelEntry, DatabaseScheduler
from djcelery import loaders
from functools import wraps
from celery import registry
from celery import schedules
#from django.db.models import Q
import datetime
#from anyjson import loads, dumps
import sys
import json
reload(sys)
sys.setdefaultencoding("utf-8")

# 处理datetime.datetime的json格式化错误.
class DateEncoder(json.JSONEncoder):  
    def default(self, obj):  
        if isinstance(obj, datetime.datetime):  
            return obj.strftime('%Y-%m-%d %H:%M:%S')  
        elif isinstance(obj, date):  
            return obj.strftime("%Y-%m-%d")  
        else:  
            return json.JSONEncoder.default(self, obj) 

def get_crontab_task(request):
    crontab_list=[] #取id使用
    crontab_array=[] #转json使用
    try:
        allTasks = PeriodicTask.objects.values() #获取任务列表
        for cron in allTasks:
            crontab_id = cron['crontab_id']
            if crontab_id != None:
                crontab_list.append(crontab_id) #获取所有的crontab id
                crontab_array.append(cron)
        allTasks_json=json.dumps(crontab_array,cls=DateEncoder)
        return render(request, 'return_value.html', {'return_value':allTasks_json})
    except Exception, e:
        return render(request, 'return_value.html', {'return_value':e})

def get_crontab_time(request): #获取定时时间列表
    crontab_array=[] #转json使用
    try:
        allTime = CrontabSchedule.objects.values() #获取定时任务时间列表
        for cron in allTime:
                crontab_array.append(cron)
        allTime_json=json.dumps(crontab_array,cls=DateEncoder)

        return render(request, 'return_value.html', {'return_value':allTime_json})

    except Exception, e:
        return render(request, 'return_value.html', {'return_value':e})

def add_crontab_time(request):
    # minute  hour  day_of_week  day_of_month  month_of_year
    minute =  request.GET.get('minute','*')
    hour =  request.GET.get('hour','*')
    day_of_week =  request.GET.get('day_of_week','*')
    day_of_month =  request.GET.get('day_of_month','*')
    month_of_year =  request.GET.get('month_of_year','*')
    try:
        res = CrontabSchedule.objects.filter(
                minute=minute,hour=hour,
                day_of_week=day_of_week,
                day_of_month=day_of_month,
                month_of_year=month_of_year)

        if res is None:
            CrontabSchedule.objects.create(
                minute=minute,hour=hour,
                day_of_week=day_of_week,
                day_of_month=day_of_month,
                month_of_year=month_of_year) #插入数据库
        else:
            return render(request, 'return_value.html', {'return_value':'已存在'})
        return render(request, 'return_value.html', {'return_value':1})
    except Exception, e:
        return render(request, 'return_value.html', {'return_value':e})


def modify_crontab_time(request):
    # minute  hour  day_of_week  day_of_month  month_of_year
    id = request.GET['id']
    minute =  request.GET.get('minute','*')
    hour =  request.GET.get('hour','*')
    day_of_week =  request.GET.get('day_of_week','*')
    day_of_month =  request.GET.get('day_of_month','*')
    month_of_year =  request.GET.get('month_of_year','*')

    '''
    schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=minute,
            hour=hour,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            month_of_year=month_of_year,
            #timezone=pytz.timezone('Canada/Pacific')
        )
    '''
    try:
        CrontabSchedule.objects.filter(id=id).update(minute=minute,hour=hour,day_of_week=day_of_week,day_of_month=day_of_month,month_of_year=month_of_year) #更新数据库
        #获取相关联的,并且是开启状态的定时任务
        cron_tasks=PeriodicTask.objects.filter(crontab_id=id,enabled=1).values() #新建定时任务
        crontab_list=[]
        for i in  cron_tasks:
            res = i['id']
            crontab_list.append(res)

        for p in crontab_list:
            task = PeriodicTask.objects.get(id=p)
            task.enabled = True #重新开启任务,触发定时更新
            task.save()

        return render(request, 'return_value.html', {'return_value':1})

    except Exception, e:
        return render(request, 'return_value.html', {'return_value':e})



def delete_crontab_time(request):
    cron_id = request.GET['id']
    try:
        CrontabSchedule.objects.filter(id=int(cron_id)).delete() #删除指定crontab

        return render(request, 'return_value.html', {'return_value':1})
    except Exception, e:
        return render(request, 'return_value.html', {'return_value':e})

def get_task_template(request):
    irrelevant_tasks = ['zlcelery.celery.debug_task',
                        'celery.backend_cleanup',
                        'celery.chain',
                        'celery.chord',
                        'celery.chord_unlock',
                        'celery.chunks',
                        'celery.group',
                        'celery.map',
                        'celery.starmap',]

    loaders.autodiscover()
    tasks = list(sorted(registry.tasks.regular().keys()))
    

    for t in irrelevant_tasks:
        tasks.remove(t)
    
    tasks_json = json.dumps(tasks)
    return render(request, 'return_value.html', {'return_value':tasks_json})

def add_crontab_task(request):
    name =  request.GET['name']
    task =  request.GET['task']
    args =  request.GET['args']
    enabled =  request.GET['enabled']
    crontab_id =  request.GET['crontab_id']

    try:
        res = PeriodicTask.objects.filter(name=name)

        if res is None:
            PeriodicTask.objects.create(name=name,task=task,args=args,enabled=enabled,crontab_id=crontab_id) #新建定时任务
        else:
            return render(request,'return_value.html','任务名称已存在')
        return render(request, 'return_value.html', {'return_value':1})
    except Exception, e:
        return render(request, 'return_value.html', {'return_value':e})


def modify_crontab_task(request):
    id = request.GET['id']
    name =  request.GET['name']
    task =  request.GET['task']
    args =  request.GET['args']
    enabled =  request.GET['enabled']
    crontab_id =  request.GET['crontab_id']

    schedule = CrontabSchedule.objects.get(pk=crontab_id)

    schedule_dict = {
        'crontab': schedule,
        'args': args,
        'task': task,
        'enabled': enabled,
        'name': name
    }

    try:
        obj, _ = PeriodicTask._default_manager.update_or_create(
            id=int(id), defaults=schedule_dict,
        )
    except Exception, e:
        return render(request,'return_value.html',{'return_value':e})

    return render(request, 'return_value.html', {'return_value':1})

