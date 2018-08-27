# -*- coding: UTF-8 -*-
from django.conf.urls import url
from scheduled_tasks import views

from scheduled_tasks import tasks as zl_tasks
urlpatterns = [
    url(r'^get_crontab_task/$', views.get_crontab_task),  # 周期任务 列表数据
    url(r'^get_crontab_time/$', views.get_crontab_time),  # 获取 crontab  定时时间
    url(r'^get_task_template/$', views.get_task_template),  # 获取 crontab 模板

    url(r'^add_crontab_time/$', views.add_crontab_time),  # 获取 crontab  定时时间
    url(r'^delete_crontab_time/$', views.delete_crontab_time),  # 删除指定 crontab  定时时间
    url(r'^modify_crontab_time/$', views.modify_crontab_time),  # 修改指定 crontab  定时时间


    url(r'^add_crontab_task/$', views.add_crontab_task),  # 新建定时任务
    url(r'^modify_crontab_task/$', views.modify_crontab_task),  # 修改定时任务
]


