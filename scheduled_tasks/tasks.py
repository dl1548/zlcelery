from __future__ import absolute_import

from celery import shared_task

from scheduled_tasks.ansible_api.get_sys_info import GetSysInfoL

import json,time



@shared_task
def add(x, y):
    return x + y

@shared_task
def get_date(ip,user,pwd):
    ip = ip
    user = user
    pwd = pwd
    get_res = GetSysInfoL(username=user,password=pwd,ip=ip)
    #get_res.get_info()
    res=get_res.get_info()
    #time.sleep(5)
    #_ret = json.loads(res)

    r_list=[]
    r_list.append(ip)
    r_list.append(user)
    r_list.append(pwd)
    
    

    return res