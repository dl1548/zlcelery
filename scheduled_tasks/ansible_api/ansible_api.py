# coding: utf-8
import json
from collections import namedtuple
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from ansible.inventory import Inventory,Host,Group
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.plugins.callback import CallbackBase
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.plugins.callback.default import CallbackModule as CallbackModule_default
from ansible import constants as C
from ansible.utils.color import colorize, hostcolor
import os
import sys

class ServerError(Exception):
    pass


class MyInventory(Inventory):

    def __init__(self, resource,loader, variable_manager):

        self.resource = resource
        self.inventory = Inventory(loader=loader,variable_manager=variable_manager)
        self.gen_inventory()

    def my_add_group(self, hosts, groupname, groupvars=None):

        my_group = Group(name=groupname)

        # if group variables exists, add them to group
        if groupvars:
            for key, value in groupvars.iteritems():
                my_group.set_variable(key, value)
        # add hosts to group
        for host in hosts:
            # set connection variables
            hostname = host.get("hostname")
            hostip = host.get('ip', hostname)
            hostport = host.get("port")
            username = host.get("username")
            password = host.get("password")
            #ssh_key = host.get("ssh_key")
            my_host = Host(name=hostname, port=hostport)
            my_host.set_variable('ansible_host', hostip)
            my_host.set_variable('ansible_port', hostport)
            my_host.set_variable('ansible_user', username)
            my_host.set_variable('ansible_ssh_pass', password)
            #my_host.set_variable('ansible_ssh_private_key_file', ssh_key)

            # set other variables
            for key, value in host.iteritems():
                if key not in ["hostname", "port", "username", "password"]:
                    my_host.set_variable(key, value)
            # add to group
            my_group.add_host(my_host)

        self.inventory.add_group(my_group)

    def gen_inventory(self):
        """
        add hosts to inventory.
        """
        if isinstance(self.resource, list):
            self.my_add_group(self.resource, 'default_group')
        elif isinstance(self.resource, dict):
            for groupname, hosts_and_vars in self.resource.iteritems():
                self.my_add_group(hosts_and_vars.get("hosts"), groupname, hosts_and_vars.get("vars"))


class ResultsCollector(CallbackBase):

    def __init__(self, *args, **kwargs):
        super(ResultsCollector, self).__init__(*args, **kwargs)
        self.host_ok = {}
        self.host_unreachable = {}
        self.host_failed = {}

    def v2_runner_on_unreachable(self, result):
        self.host_unreachable[result._host.get_name()] = result

    def v2_runner_on_ok(self, result,  *args, **kwargs):
        self.host_ok[result._host.get_name()] = result

    def v2_runner_on_failed(self, result,  *args, **kwargs):
        self.host_failed[result._host.get_name()] = result



class CallbackModuleDE(CallbackBase):

    '''
    This is the default callback interface, which simply prints messages
    to stdout when new callback events are received.
    '''

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'stdout'
    CALLBACK_NAME = 'default'

    def __init__(self,**kwargs):

        self._play = None
        self._last_task_banner = None
        self.log_path = kwargs.get('log_path','/tmp/ansible_callback.log')
        super(CallbackModuleDE, self).__init__()
        self.host_ok = {}
        self.host_unreachable = {}
        self.host_failed = {}
        self.error_msg = {}
        self.result = ''
        self.stdout_re={}

    def _write_log(self,str):
        if self.log_path:
            if not os.path.exists(self.log_path):
                f=open(self.log_path,'w')
                import  datetime
                f.write(u'###start deploy:' + datetime.datetime.now())
                f.close()
            self.result +=str + '\n'
            f = open(self.log_path, 'a')
            f.write(str+"\n")
            f.close()



    def v2_runner_on_failed(self, result, ignore_errors=False):

        self.host_failed[result._host.get_name()] = result

        if self._play.strategy == 'free' and self._last_task_banner != result._task._uuid:
            self._print_task_banner(result._task)


        delegated_vars = result._result.get('_ansible_delegated_vars', None)
        #self._handle_exception(result._result)


        self._handle_warnings(result._result)
        if C.COMMAND_WARNINGS and 'warnings' in result._result and result._result['warnings']:
            for warning in result._result['warnings']:
                self._write_log(warning)


        if result._task.loop and 'results' in result._result:
            self._process_items(result)

        else:
            if delegated_vars:
                self._display.display("fatal: [%s -> %s]: FAILED! => %s" % (result._host.get_name(), delegated_vars['ansible_host'], self._dump_results(result._result)), color=C.COLOR_ERROR)
                self._write_log("fatal: [%s -> %s]: FAILED! => %s" % (result._host.get_name(), delegated_vars['ansible_host'], self._dump_results(result._result)))

                self.error_msg[result._host.get_name()]=self._dump_results(result._result)

            else:
                self._display.display("fatal: [%s]: FAILED! => %s" % (result._host.get_name(), self._dump_results(result._result)), color=C.COLOR_ERROR)
                self._write_log("fatal: [%s]: FAILED! => %s" % (result._host.get_name(), self._dump_results(result._result)))

                self.error_msg[result._host.get_name()] =self._dump_results(result._result)


        if ignore_errors:
            self._display.display("...ignoring", color=C.COLOR_SKIP)
            self._write_log("...ignoring")

    def v2_runner_on_ok(self, result):
        self.host_ok[result._host.get_name()] = result
        #logger.debug(result._result)
        _tmp_re= result._result['invocation']

        #self.result += str(result._result)
        if  dict(_tmp_re).has_key('module_name'):
            if result._result['invocation']['module_name']  not in ['fetch','copy']:

                self.stdout_re[result._host.get_name()]=[result._result['invocation']['module_args']['_raw_params'],result._result['stdout']]


        if self._play.strategy == 'free' and self._last_task_banner != result._task._uuid:

            self._print_task_banner(result._task)


        self._clean_results(result._result, result._task.action)

        delegated_vars = result._result.get('_ansible_delegated_vars', None)
        self._clean_results(result._result, result._task.action)
        if result._task.action in ('include', 'include_role'):
            return
        elif result._result.get('changed', False):
            if delegated_vars:
                msg = "changed: [%s -> %s]" % (result._host.get_name(), delegated_vars['ansible_host'])
            else:
                msg = "changed: [%s]" % result._host.get_name()
            color = C.COLOR_CHANGED
        else:
            if delegated_vars:
                msg = "ok: [%s -> %s]" % (result._host.get_name(), delegated_vars['ansible_host'])
            else:
                msg = "ok: [%s]" % result._host.get_name()
            color = C.COLOR_OK

        self._handle_warnings(result._result)

        if C.COMMAND_WARNINGS and 'warnings' in result._result and result._result['warnings']:
            for warning in result._result['warnings']:
                self._write_log(warning)


        if result._task.loop and 'results' in result._result:
            self._process_items(result)

        else:

            if (self._display.verbosity > 0 or '_ansible_verbose_always' in result._result) and not '_ansible_verbose_override' in result._result:
                msg += " => %s" % (self._dump_results(result._result),)
            self._write_log(msg)
            self._display.display(msg, color=color)

    def v2_runner_on_skipped(self, result):
        if C.DISPLAY_SKIPPED_HOSTS:
            if self._play.strategy == 'free' and self._last_task_banner != result._task._uuid:
                self._print_task_banner(result._task)


            if result._task.loop and 'results' in result._result:
                self._process_items(result)

            else:
                msg = "skipping: [%s]" % result._host.get_name()
                if (self._display.verbosity > 0 or '_ansible_verbose_always' in result._result) and not '_ansible_verbose_override' in result._result:
                    msg += " => %s" % self._dump_results(result._result)
                self._write_log(msg)
                self._display.display(msg, color=C.COLOR_SKIP)

    def v2_runner_on_unreachable(self, result):
        self.host_unreachable[result._host.get_name()] = result

        if self._play.strategy == 'free' and self._last_task_banner != result._task._uuid:
            self._print_task_banner(result._task)

        delegated_vars = result._result.get('_ansible_delegated_vars', None)
        if delegated_vars:
            self._display.display("fatal: [%s -> %s]: UNREACHABLE! => %s" % (result._host.get_name(), delegated_vars['ansible_host'], self._dump_results(result._result)), color=C.COLOR_UNREACHABLE)
            self._write_log("fatal: [%s -> %s]: UNREACHABLE! => %s" % (result._host.get_name(), delegated_vars['ansible_host'], self._dump_results(result._result)))

            self.error_msg[result._host.get_name()] = self._dump_results(result._result)
        else:
            self._display.display("fatal: [%s]: UNREACHABLE! => %s" % (result._host.get_name(), self._dump_results(result._result)), color=C.COLOR_UNREACHABLE)
            self._write_log("fatal: [%s]: UNREACHABLE! => %s" % (result._host.get_name(), self._dump_results(result._result)))

            self.error_msg[result._host.get_name()] = self._dump_results(result._result)

    def v2_playbook_on_no_hosts_matched(self):
        self._display.display("skipping: no hosts matched", color=C.COLOR_SKIP)
        self._write_log("skipping: no hosts matched")

    def v2_playbook_on_no_hosts_remaining(self):
        self._display.banner("NO MORE HOSTS LEFT")
        self._write_log("NO MORE HOSTS LEFT")

    def v2_playbook_on_task_start(self, task, is_conditional):

        if self._play.strategy != 'free':
            self._print_task_banner(task)

    def _print_task_banner(self, task):
        # args can be specified as no_log in several places: in the task or in
        # the argument spec.  We can check whether the task is no_log but the
        # argument spec can't be because that is only run on the target
        # machine and we haven't run it thereyet at this time.
        #
        # So we give people a config option to affect display of the args so
        # that they can secure this if they feel that their stdout is insecure
        # (shoulder surfing, logging stdout straight to a file, etc).
        args = ''
        if not task.no_log and C.DISPLAY_ARGS_TO_STDOUT:
            args = u', '.join(u'%s=%s' % a for a in task.args.items())
            args = u' %s' % args

        self._display.banner(u"TASK [%s%s]" % (task.get_name().strip(), args))
        self._write_log(u"TASK [%s%s]" % (task.get_name().strip(), args))
        if self._display.verbosity >= 2:
            path = task.get_path()
            if path:
                self._display.display(u"task path: %s" % path, color=C.COLOR_DEBUG)
                self._write_log(u"task path: %s" % path)

        self._last_task_banner = task._uuid

    def v2_playbook_on_cleanup_task_start(self, task):
        self._display.banner("CLEANUP TASK [%s]" % task.get_name().strip())
        self._write_log("CLEANUP TASK [%s]" % task.get_name().strip())

    def v2_playbook_on_handler_task_start(self, task):
        self._display.banner("RUNNING HANDLER [%s]" % task.get_name().strip())
        self._write_log("RUNNING HANDLER [%s]" % task.get_name().strip())

    def v2_playbook_on_play_start(self, play):
        name = play.get_name().strip()
        if not name:
            msg = u"PLAY"
        else:
            msg = u"PLAY [%s]" % name

        self._play = play

        self._display.banner(msg)
        self._write_log(msg)

    def v2_on_file_diff(self, result):
        if result._task.loop and 'results' in result._result:
            for res in result._result['results']:
                if 'diff' in res and res['diff'] and res.get('changed', False):
                    diff = self._get_diff(res['diff'])
                    if diff:
                        self._display.display(diff)
                        self._write_log(diff)
        elif 'diff' in result._result and result._result['diff'] and result._result.get('changed', False):
            diff = self._get_diff(result._result['diff'])
            if diff:
                self._display.display(diff)
                self._write_log(diff)

    def v2_runner_item_on_ok(self, result):
        delegated_vars = result._result.get('_ansible_delegated_vars', None)
        if result._task.action in ('include', 'include_role'):
            return
        elif result._result.get('changed', False):
            msg = 'changed'
            color = C.COLOR_CHANGED
        else:
            msg = 'ok'
            color = C.COLOR_OK

        if delegated_vars:
            msg += ": [%s -> %s]" % (result._host.get_name(), delegated_vars['ansible_host'])
        else:
            msg += ": [%s]" % result._host.get_name()

        msg += " => (item=%s)" % (self._get_item(result._result),)

        if (self._display.verbosity > 0 or '_ansible_verbose_always' in result._result) and not '_ansible_verbose_override' in result._result:
            msg += " => %s" % self._dump_results(result._result)
        self._display.display(msg, color=color)
        self._write_log(msg)

    def v2_runner_item_on_failed(self, result):

        delegated_vars = result._result.get('_ansible_delegated_vars', None)
        #self._handle_exception(result._result)

        msg = "failed: "
        if delegated_vars:
            msg += "[%s -> %s]" % (result._host.get_name(), delegated_vars['ansible_host'])
        else:
            msg += "[%s]" % (result._host.get_name())

        self._handle_warnings(result._result)
        self._display.display(msg + " (item=%s) => %s" % (self._get_item(result._result), self._dump_results(result._result)), color=C.COLOR_ERROR)
        self._write_log(msg + " (item=%s) => %s" % (self._get_item(result._result), self._dump_results(result._result)))
    def v2_runner_item_on_skipped(self, result):
        if C.DISPLAY_SKIPPED_HOSTS:
            msg = "skipping: [%s] => (item=%s) " % (result._host.get_name(), self._get_item(result._result))
            if (self._display.verbosity > 0 or '_ansible_verbose_always' in result._result) and not '_ansible_verbose_override' in result._result:
                msg += " => %s" % self._dump_results(result._result)
            self._display.display(msg, color=C.COLOR_SKIP)
            self._write_log(msg)

    def v2_playbook_on_include(self, included_file):
        msg = 'included: %s for %s' % (included_file._filename, ", ".join([h.name for h in included_file._hosts]))
        self._display.display(msg, color=C.COLOR_SKIP)
        self._write_log(msg)

    def v2_playbook_on_stats(self, stats):
        self._display.banner("PLAY RECAP")
        self._write_log("PLAY RECAP")

        hosts = sorted(stats.processed.keys())
        for h in hosts:
            t = stats.summarize(h)

            self._display.display(u"%s : %s %s %s %s" % (
                hostcolor(h, t),
                colorize(u'ok', t['ok'], C.COLOR_OK),
                colorize(u'changed', t['changed'], C.COLOR_CHANGED),
                colorize(u'unreachable', t['unreachable'], C.COLOR_UNREACHABLE),
                colorize(u'failed', t['failures'], C.COLOR_ERROR)),
                screen_only=True
            )
            self._write_log(u"%s -- %s : %s %s %s %s" % (
                'DONE',
                hostcolor(h, t),
                colorize(u'ok', t['ok'], C.COLOR_OK),
                colorize(u'changed', t['changed'], C.COLOR_CHANGED),
                colorize(u'unreachable', t['unreachable'], C.COLOR_UNREACHABLE),
                colorize(u'failed', t['failures'], C.COLOR_ERROR)))

            self._display.display(u"%s : %s %s %s %s" % (
                hostcolor(h, t, False),
                colorize(u'ok', t['ok'], None),
                colorize(u'changed', t['changed'], None),
                colorize(u'unreachable', t['unreachable'], None),
                colorize(u'failed', t['failures'], None)),
                log_only=True
            )

        self._display.display("", screen_only=True)

        # print custom stats
        if C.SHOW_CUSTOM_STATS and stats.custom:
            self._display.banner("CUSTOM STATS: ")
            # per host
            #TODO: come up with 'pretty format'
            for k in sorted(stats.custom.keys()):
                if k == '_run':
                    continue
                self._display.display('\t%s: %s' % (k, self._dump_results(stats.custom[k], indent=1).replace('\n','')))

            # print per run custom stats
            if '_run' in stats.custom:
                self._display.display("", screen_only=True)
                self._display.display('\tRUN: %s' % self._dump_results(stats.custom['_run'], indent=1).replace('\n',''))
            self._display.display("", screen_only=True)

    def v2_playbook_on_start(self, playbook):
        if self._display.verbosity > 1:
            from os.path import basename
            self._display.banner("PLAYBOOK: %s" % basename(playbook._file_name))
            self._write_log("PLAYBOOK: %s" % basename(playbook._file_name))

        if self._display.verbosity > 3:
            if self._options is not None:
                for option in dir(self._options):
                    if option.startswith('_') or option in ['read_file', 'ensure_value', 'read_module']:
                        continue
                    val =  getattr(self._options,option)
                    if val:
                        self._display.vvvv('%s: %s' % (option,val))

    def v2_runner_retry(self, result):
        task_name = result.task_name or result._task
        msg = "FAILED - RETRYING: %s (%d retries left)." % (task_name, result._result['retries'] - result._result['attempts'])
        if (self._display.verbosity > 2 or '_ansible_verbose_always' in result._result) and not '_ansible_verbose_override' in result._result:
            msg += "Result was: %s" % self._dump_results(result._result)
        self._display.display(msg, color=C.COLOR_DEBUG)
        self._write_log(msg)

class MyRunner(object):
    """
    This is a General object for parallel execute modules.
    """
    def __init__(self, resource, *args, **kwargs):
        self.resource = resource
        self.inventory = None
        self.variable_manager = None
        self.loader = None
        self.options = None
        self.passwords = None
        self.callback = None
        self.results_raw = {}
        self.timeout = kwargs.get('timeout','') if kwargs.get('timeout','') else 10
        self.forks = kwargs.get('forks','') if kwargs.get('timeout','') else 10
        self.connection =  kwargs.get('connection','') if kwargs.get('connection','') else 'smart'
        self.become_user= kwargs.get('become_user','') if kwargs.get('become_user','') else 'root'

        os = kwargs.get('os','')

        self.__initializeData()


    def __initializeData(self):
        """
        初始化ansible
        """
        Options = namedtuple('Options', ['connection','module_path', 'forks', 'timeout',  'remote_user',
                'ask_pass', 'private_key_file', 'ssh_common_args', 'ssh_extra_args', 'sftp_extra_args',
                'scp_extra_args', 'become', 'become_method', 'become_user', 'ask_value_pass', 'verbosity',
                'check', 'listhosts', 'listtasks', 'listtags', 'syntax','environment'])

        # initialize needed objects
        self.variable_manager = VariableManager()

        self.loader = DataLoader()
        self.options = Options(connection=self.connection, module_path=None, forks=self.forks, timeout=self.timeout,
                remote_user=u'root', ask_pass=False, private_key_file=None, ssh_common_args=None, ssh_extra_args=None,
                sftp_extra_args=None, scp_extra_args=None, become=u'yes', become_method=u'sudo',
                become_user=self.become_user, ask_value_pass=False, verbosity=None, check=False, listhosts=False,
                listtasks=False, listtags=False, syntax=False,environment={'LANG':'zh_CN.UTF-8','LC_CTYPE':'zh_CN.UTF-8'})
        self.passwords = dict(sshpass=None, becomepass=None)
        self.inventory = MyInventory(self.resource, self.loader, self.variable_manager).inventory
        self.variable_manager.set_inventory(self.inventory)


    def run(self, host_list, module_name, module_args,**kwargs):
        """
        run module from andible ad-hoc.
        module_name: ansible module_name
        module_args: ansible module args
        """
        # create play with tasks
        log_path = kwargs.get('log_path', '')
        async_time = kwargs.get('async_time', 0)

        play_source = dict(
                name="Ansible Play",
                hosts=host_list,
                gather_facts='no',
                tasks=[dict(action=dict(module=module_name, args=module_args))]
        )

        if async_time >0:
            play_source['tasks']=[dict(action=dict(module=module_name, args=module_args),async=async_time)]


        play = Play().load(play_source, variable_manager=self.variable_manager, loader=self.loader)
        # actually run it
        tqm = None
        self.callback = CallbackModuleDE(log_path=log_path)
        try:
            tqm = TaskQueueManager(
                    inventory=self.inventory,
                    variable_manager=self.variable_manager,
                    loader=self.loader,
                    options=self.options,
                    passwords=self.passwords,
            )
            tqm._stdout_callback = self.callback
            result=tqm.run(play)
        finally:
            if tqm is not None:
                tqm.cleanup()


    def run_playbook(self,yml_path,groups,**kwargs):
        """
        run ansible palybook
        """
        log_path = kwargs.get('log_path','')
        # self.callback = ResultsCollector()
        self.callback = CallbackModuleDE(log_path=log_path)
        filenames = yml_path  # playbook的路径


        if not os.path.exists(filenames):

            raise ServerError(u'%s yml 不存在' % (filenames))

            # template_file = TEMPLATE_DIR            #模板文件的路径
            # if not os.path.exists(template_file):
            #    logger.error('%s 路径不存在 '%template_file)
            #   sys.exit()
            #
            #            extra_vars = {}     #额外的参数 sudoers.yml以及模板中的参数，它对应ansible-playbook test.yml --extra-vars "host='aa' name='cc' "
            #            host_list_str = ','.join([item for item in host_list])
            #            extra_vars['host_list'] = host_list_str
            #            extra_vars['username'] = role_name
            #            extra_vars['template_dir'] = template_file
            #            extra_vars['command_list'] = temp_param.get('cmdList')
            #            extra_vars['role_uuid'] = 'role-%s'%role_uuid
            #            self.variable_manager.extra_vars = extra_vars
            #            logger.info('playbook 额外参数:%s'%self.variable_manager.extra_vars)

        if len(self.variable_manager.extra_vars) >0:
            extra_vars=self.variable_manager.extra_vars
        else:
            extra_vars = {}
        extra_vars['groups'] = groups
        self.variable_manager.extra_vars = extra_vars
        # actually run it
        executor = PlaybookExecutor(
            playbooks=filenames,
            inventory=self.inventory,
            variable_manager=self.variable_manager,
            loader=self.loader,
            options=self.options,
            passwords=self.passwords,
        )

        executor._tqm._stdout_callback = self.callback
        executor.run()


    def get_result(self):

        return self.callback.result,self.callback.error_msg,\
               self.callback.stdout_re

    def get_json_result(self):
        self.results_raw = {'success':{}, 'failed':{}, 'unreachable':{}}

        for host, result in self.callback.host_ok.items():
            self.results_raw['success'][host] = result._result
        for host, result in self.callback.host_failed.items():
            if result._result.has_key('msg'):

                self.results_raw['failed'][host] = result._result['msg']
            else:
                if result._result.has_key('stderr'):

                    self.results_raw['failed'][host] = result._result['stderr']

        for host, result in self.callback.host_unreachable.items():
            self.results_raw['unreachable'][host]= result._result['msg']

        return self.results_raw
