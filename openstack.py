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
    VAR_TO_ARG = {
        'OS_USERNAME': 'username',
        'OS_PASSWORD': 'api_key',
        'OS_AUTH_URL': 'auth_url',
        'OS_TENANT_NAME': 'project_id',
        'NOVACLIENT_INSECURE': 'insecure'
    }
    OS_AUTH = {'version': 2}
    USER_CONF = {}

    def check_config(self, mess):
        '''Check to see if the user has selected a project.

        If there is only one project, it will be selected automatically.

        :param mess: Errbot message object
        '''
        configs = self.get_config_files()
        if len(configs) == 1:
            # there is only one project, so auto-select it
            self.set_config(mess, list(configs)[0])

        if self.USER_CONF.get(mess.frm.person):
            project_id = self.USER_CONF[mess.frm.person]['project_id']
            message = '/me Openstack project: {}'.format(project_id)
            self.send(mess.frm, message, message_type=mess.type)
        else:
            raise Exception('You have not selected a project. Run "nova '
                            'project list" to see a list of available '
                            'projects and then use "nova project set '
                            '<name>" to select one')

    def read_config_file(self, config_file):
        '''read contents of config file into a dict of key-> val pairs

        :param str config_file: name of openrc config file
        :return: configuration key-values
        :rtype: dict
        '''
        with open(os.path.join(CONFIG_DIR, config_file)) as f:
            lines = f.read().splitlines()  # drop newline chars

        reg = re.compile(r'export (?P<var>\w+)(?:=(?P<value>.+))*')
        result = {}
        for line in lines:
            try:
                var, value = reg.match(line).groups()
                arg = self.VAR_TO_ARG[var]
            except (KeyError, AttributeError):
                pass
            else:
                value = value.strip('\'"')  # unquote the value
                if arg == 'insecure':
                    value = False if value in ('False', 'false') else True
                result[arg] = value

        return result

    def get_config_files(self):
        '''Get openrc config(s)

        :return: config paths by project name
        :rtype: dict
        '''
        search_path = os.path.join(CONFIG_DIR, '*-openrc.sh')
        configs = glob.glob(search_path)
        if not configs:
            raise Exception('No openrc files found at: {}'.format(search_path))

        result = {}
        for config in configs:
            contents = self.read_config_file(config)
            result[contents['project_id']] = config

        return result

    def set_config(self, mess, project_name):
        '''Sets config to selected openrc file.

        :param mess: Errbot message object
        :param str project_name: name of openstack project
        '''
        config_file = self.get_config_files().get(project_name)
        if config_file:
            config = self.read_config_file(config_file)
            self.USER_CONF[mess.frm.person] = dict(self.OS_AUTH, **config)
            message = '/me Selected Openstack project: {} for {}'
        else:
            message = '/me No such project {!r}'.format(project_name)
        self.send(mess.frm,
                  message.format(project_name, mess.frm.person),
                  message_type=mess.type)

    @botcmd(split_args_with=None)
    def nova_project(self, mess, args):
        '''nova project list/set'''
        if not args:
            self.check_config(mess)
            project_id = self.USER_CONF[mess.frm.person]['project_id']
            return 'Current project: {}'.format(project_id)

        if args[0] == 'list':
            return '\n'.join(self.get_config_files())
        elif args[0] == 'set':
            self.set_config(mess, args[1])

    @botcmd
    def nova_list(self, mess, args):
        '''List VMs'''
        self.check_config(mess)
        message = '/me is getting the list of VMs for project {}'
        project_id = self.USER_CONF[mess.frm.person]['project_id']
        self.send(mess.frm, message.format(project_id), message_type=mess.type)

        nova_client = Client(**self.USER_CONF[mess.frm.person])
        vms = nova_client.servers.list()

        pt = PrettyTable(['ID', 'Name', 'Status', 'Networks'])
        pt.align = 'l'

        network = '{}: {}'.format
        csv = ', '.join
        for vm in vms:
            networks = []
            for name, ips in vm.networks.items():
                networks.append(network(name, csv(ips)))
            all_networks = '; '.join(networks)
            pt.add_row([vm.id, vm.name, vm.status, all_networks])

        return '/code {}'.format(pt)

    @botcmd
    @arg_botcmd('vm', type=str)
    def nova_show(self, mess, vm):
        '''Show VM details'''
        self.check_config(mess)
        message = '/me is getting the list of VMs for project {}'
        project_id = self.USER_CONF[mess.frm.person]['project_id']
        self.send(mess.frm, message.format(project_id), message_type=mess.type)

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

    def _get_name_from_id(self, mess, type_, id_):
        # Return the name of a nova client resource for a given person given
        # the type and id of the resource.
        try:
            nova_client = Client(**self.USER_CONF[mess.frm.person])
            resource = getattr(nova_client, type_)[id_]
            return resource.name
        except Exception:
            return 'Error fetching name'

    def get_image(self, mess, image_id):
        '''Get the image name from the ID

        :param mess: Errbot message object
        :param str image_id: id of openstack image
        :return: name of image
        :rtype: str
        '''
        return self._get_name_from_id(mess, 'images', image_id)

    def get_flavor(self, mess, flavor_id):
        '''Get the flavor name from the ID

        :param mess: Errbot message object
        :param str flavor_id: id of openstack image
        :return: name of image
        :rtype: str
        '''
        return self._get_name_from_id(mess, 'flavors', flavor_id)
