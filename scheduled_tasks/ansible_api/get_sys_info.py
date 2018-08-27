# coding: utf-8
from remote_run_api import remote_run_cmd

import os


#linux
class GetSysInfoL():
    def __init__(self,username,password,ip,os_type='Linux'):
        self.username = username
        self.password = password
        self.ip = ip
        self.os_type = os_type


    def get_info(self):
        #script_path = '/root/celery/zlcelery/zl/ansible_api/script/'
        script_path = os.path.dirname(__file__) + '/script/'
        re_run = remote_run_cmd(ip=self.ip,username=self.username,
            password=self.password,os_type=self.os_type)

        _ret=re_run.run_script(script_path + 'test.sh','')

        return  _ret

