'''
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''
import glob
import os
import re

from errbot import BotPlugin, botcmd, arg_botcmd
from novaclient.client import Client
from prettytable import PrettyTable


CONFIG_DIR = os.path.expanduser('~/.nova')


class Openstack(BotPlugin):
    '''Openstack plugin for Errbot.

    This module is designed to be similar to using the nova CLI tool.
    '''
    OS_ARGS = ['username', 'api_key', 'auth_url', 'project_id']
    OS_ATTRS = ['OS_USERNAME', 'OS_PASSWORD', 'OS_AUTH_URL', 'OS_TENANT_NAME']
    OS_AUTH = {'version': 2}
    USER_CONF = {}

    def check_config(self, mess):
        '''Check to see if the user has selected a project. If there is only
        one project, it will be selected automatically

        :param mess: Errbot message object
        '''
        configs = self.get_config_files()
        if len(configs.keys()) == 1:
            # there is only one project, so auto-select it
            self.set_config(mess, list(configs.keys())[0])

        if self.USER_CONF.get(mess.frm.person):
            self.send(mess.frm,
                      '/me Openstack project: {}'
                      .format(self.USER_CONF[mess.frm.person]['project_id']),
                      message_type=mess.type)
        else:
            raise Exception('You have not selected a project. Run "nova '
                            'project list" to see a list of available '
                            'projects and then use "nova project set '
                            '<name>" to select one')

    def read_config_file(self, config_file):
        '''read contents of config file into a dict of key-> val pairs

        :param config_file: name of openrc config file
        :returns: dinctionary of configuration items
        '''
        result = {}
        reg = re.compile('export (?P<name>\w+)(\=(?P<value>.+))*')
        for line in open(os.path.join(CONFIG_DIR, config_file)):
            match = reg.match(line)
            if match:
                var = match.group('name')
                val = match.group('value')
                if var in self.OS_ATTRS:
                    key = dict(zip(self.OS_ATTRS, self.OS_ARGS)).get(var)
                    result[key] = val.strip('"').strip('\'')
        return result

    def get_config_files(self):
        '''Get openrc config(s)

        :returns: result: dictionary of project name as key and config path as
                          value
        '''
        result = {}
        conf = glob.glob(os.path.join(CONFIG_DIR, '*-openrc.sh'))
        if len(conf) < 1:
            raise Exception('No openrc files found at: {}'
                            .format(os.path.join(CONFIG_DIR, '*-openrc.sh')))

        for c in conf:
            contents = self.read_config_file(c)
            result[contents['project_id']] = c

        return result

    def set_config(self, mess, project_name):
        '''Sets config to selected openrc file

        :param mess: Errbot message object
        :param project_name: name of openstack project
        '''
        config_file = self.get_config_files()[project_name]
        self.USER_CONF[mess.frm.person] = self.OS_AUTH.copy()
        self.USER_CONF[mess.frm.person].update(
                self.read_config_file(config_file)
            )

        self.send(mess.frm,
                  '/me Selected Openstack project: {} for {}'
                  .format(project_name, mess.frm.person),
                  message_type=mess.type)

    @botcmd(split_args_with=None)
    def nova_project(self, mess, args):
        '''nova project list/set'''
        if len(args) == 0:
            self.check_config(mess)
            return ('Current project: {}'
                    .format(self.USER_CONF[mess.frm.person]['project_id']))
        if args[0] == 'list':
            return '\n'.join([k for k in self.get_config_files().keys()])
        elif args[0] == 'set':
            self.set_config(mess, args[1])

    @botcmd
    def nova_list(self, mess, args):
        '''List VMs'''
        self.check_config(mess)
        self.send(mess.frm,
                  '/me is getting the list of VMs for project {}'
                  .format(self.USER_CONF[mess.frm.person]['project_id']),
                  message_type=mess.type)

        nova_client = Client(**self.USER_CONF[mess.frm.person])
        vms = nova_client.servers.list()

        pt = PrettyTable(['ID', 'Name', 'Status', 'Networks'])
        pt.align = 'l'

        for vm in vms:
            for key, val in vm.networks.items():
                network = '{}: {}'.format(key, ', '.join(val))

            pt.add_row([vm.id, vm.name, vm.status, network])

        return '/code {}'.format(pt)

    @botcmd
    @arg_botcmd('vm', type=str)
    def nova_show(self, mess, vm):
        '''Show VM details'''
        self.check_config(mess)
        self.send(mess.frm,
                  '/me is getting the list of VMs for project {}'
                  .format(self.USER_CONF[mess.frm.person]['project_id']),
                  message_type=mess.type)
        nova_client = Client(**self.USER_CONF[mess.frm.person])
        vm = nova_client.servers.get(vm)

        pt = PrettyTable(['Key', 'Value'])
        pt.align = 'l'

        vm = sorted(vm.to_dict().items())

        for key, val in vm:
            if key in ['links', 'addresses']:
                continue
            if key == 'image':
                val = self.get_image(mess, val['id'])
            if key == 'flavor':
                val = self.get_flavor(mess, val['id'])
            if key == 'networks':
                for k, v in val.items():
                    val = '{}: {}'.format(k, ', '.join(v))
            if key == 'security_groups':
                val = ', '.join([k['name'] for k in val])

            pt.add_row([key, val])

        return '/code {}'.format(pt)

    def get_image(self, mess, image_id):
        '''get the image name from the ID

        :param mess: Errbot message object
        :param image_id: id of openstack image
        :returns name: name of image
        '''
        try:
            nova_client = Client(**self.USER_CONF[mess.frm.person])
            image = nova_client.images.get(image_id)
            name = image.name
        except Exception:
            name = 'Error fetching name'
        return name

    def get_flavor(self, mess, flavor_id):
        '''get the flavor name from the ID

        :param mess: Errbot message object
        :param flavor_id: id of openstack image
        :returns name: name of image
        '''
        try:
            nova_client = Client(**self.USER_CONF[mess.frm.person])
            flavor = nova_client.flavors.get(flavor_id)
            name = flavor.name
        except Exception:
            name = 'Error fetching name'
        return name

