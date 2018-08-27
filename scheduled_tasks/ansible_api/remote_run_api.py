# coding: utf-8
from ansible_api import MyInventory,MyRunner

class ServerError(Exception):
    pass



class remote_run_cmd():
    def __init__(self,**kwargs):
        '''
        :param hostid:
        :param type  cmd, script,scp_file,fetch_file:
        :param kwargs:
        '''

        self.ip = kwargs.get('ip','')
        self.username = kwargs.get('username','')
        self.password = kwargs.get('password','')
        self.port = kwargs.get('port',22)
        self.raw = kwargs.get('raw',False)
        self.run_user = kwargs.get('run_user','root')
        self.time_out = kwargs.get('time_out',10)
        self.Linux={}
        self.Windows=[]
        self.islinux=[]
        self.iswindows=[]
        self.iserrhost=[]
        self.os_type=kwargs.get('os_type','Linux')

        if not self.os_type :
            raise ServerError('OS TYPEY 没有配置')

        if not self.ip:
            raise ServerError('ip 没有配置')


        host_list = {}
        tmp_group = {}
        tmp_group['hosts'] = []

        if self.os_type == 'Linux':
            if not self.username or not self.password:
                raise ServerError('账号，密码 请配置完整')


            _list = {}
            _list['hostname'] = self.ip
            _list['port'] = self.port
            _list['username'] = self.username
            _list['password'] = self.password
            tmp_group['hosts'].append(_list)
            pass

        host_list['tmp_group'] = tmp_group
        self.Linux=host_list


    def run_cmd(self,cmd,**kwargs):
        cwd=kwargs.get('cwd','')

        s=''
        if cmd:
            cmd_re = ''

            if len(self.Linux['tmp_group']['hosts'])>0:
                ansible_run = MyRunner(self.Linux,become_user=self.run_user, timeout=self.time_out)
                ansible_run.run('tmp_group', 'shell',
                                'source /etc/profile;'+cmd +' chdir='+cwd if cwd else cmd )
                result,error,stdout=ansible_run.get_result()

                if len(error) >0:
                    raise ServerError(error)

                if self.raw:
                    cmd_re=stdout
                else:
                    for k,v in stdout.items():
                        cmd_re=v[1]
                pass

            return cmd_re

        pass
    def run_script(self,script,options):

        cmd_re = ''


        if len(self.Linux['tmp_group']['hosts']) > 0:
            ansible_run =MyRunner(self.Linux,become_user=self.run_user, timeout=self.time_out)
            ansible_run.run('tmp_group', 'script', script + ' ' + options)
            result, error, stdout = ansible_run.get_result()

            if len(error) > 0:
                raise ServerError(error)

            if self.raw:
                cmd_re = stdout
            else:
                for k, v in stdout.items():
                    cmd_re = v[1]
            pass

        return cmd_re

        