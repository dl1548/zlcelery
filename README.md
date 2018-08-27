
Django (1.11.11)
celery (3.1.26.post2)
django-celery (3.2.2)


应用 为 scheduled_tasks 

启动celery:
export PYTHONOPTIMIZE=1 && celery -A zlcelery worker --autoreload -l info -B



#### 获取所有定时任务

`url : scheduled_tasks/get_crontab_task/`

#### 获取所有 定时任务时间 

`url : scheduled_tasks/get_crontab_time/`

#### 获取定时任务模板

`url : scheduled_tasks/get_task_template/`

#### 添加定时任务时间

格式同crontab格式.五个值,不传递,默认存值为 * (星号)

minute  hour  day_of_week  day_of_month  month_of_year

`url : scheduled_tasks/add_crontab/`

#### 修改定时任务时间

格式同crontab格式.六个值,不传递,默认存值为 * (星号)
id minute  hour  day_of_week  day_of_month  month_of_year

经测试,修改时间不会动态生效.就是说,时间的修改对当前运行的任务不会即时生效.
两种方法触发生效.1: 重启服务 2: 相关任务重新启动(建议)

`url : scheduled_tasks/modify_crontab_time/`

修改的同时,要查询所有的关联此crontab的任务,且任务是开启状态的.后重新更新下任务,才能触发任务的定时的更新.(后台已做好)


#### 删除定时任务时间

需要一个参数定时任务时间 的id.
如果要批量删除,就修改为传递列表.后台也要修改.

注意:时间删除,关联的任务也会全部删除!

`url : scheduled_tasks/delete_crontab/`


#### 新加定时任务

需要五个参数:
name : 名称,用户自定义 (唯一!) 
task : 任务模板(通过模板url可取出)
args : 参数,视情况而定(不同任务可能传参不同)
enabled : 1 开启     0 关闭
crontab_id :定时任务时间ID 

`url : scheduled_tasks/add_crontab_task/`


#### 修改定时任务

通过ID修改.(与新加不同,新建要判断的是name,修改是通过id,虽然理论上name也是唯一的
,但是修改可能是修改name,所以通过id)

需要六个参数:
id : 任务id
name : 名称,用户自定义 (唯一!) 
task : 任务模板(通过模板url可取出)
args : 参数,视情况而定(不同任务可能传参不同)
enabled : 1 开启     0 关闭
crontab_id :定时任务时间ID 

`url : scheduled_tasks/modify_crontab_task/`

