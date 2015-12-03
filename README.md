Errbot Openstack Plugin
=======================

This Errbot plugin allows users to list or show VMs in one or more Openstack projects.


Available commands for nova
---------------------------

Available commands for Openstack

• !nova list - List VMs
• !nova project - nova project list/set
• !nova show - usage: nova_show [-h] vm

Requirements
------------

 - Python ~> 3.4
 - python-novaclient ~> 2.31.0
 - prettytable ~> 0.7.2


Installation
------------

If you have the appropriate administrative privileges, you can install err-openstack from chat...

    !repos install https://github.com/jgrill/err-openstack.git

You can also git clone into your Errbot's plugin directory. Use pip to install requirements...

    $ cd /path/to/errbot/plugins
    $ git clone https://github.com/jgrill/err-openstack.git
    $ cd err-openstack
    $ pip install -r requirements.txt

Configuration
-------------

Create a `.nova` directory in the Errbot user's home directory. Download your `[project-name]-openrc.sh` file from your Openstack instance into this directory.

Err-openstack can support multiple Openstack API accounts. Simply download each openrc file into your `.nova` directory.

You will need to hardcode your password into each openrc file. Open each openrc file in your favorite editor and...

...remove these three lines:

    echo "Please enter your OpenStack Password: "
    read -sr OS_PASSWORD_INPUT
    export OS_PASSWORD=$OS_PASSWORD_INPUT

...add the following line (use your actual password):

    export OS_PASSWORD="YOUR-PASSWORD-HERE"

Usage
-----

See `!help Openstack` for general usage.

If you have more than one Openstack account, Errbot will tell you to select one. Selection is accomplished using the `!nova project` commands, e.g.

    !nova project list

      project-1
      project-2
      project-3

    !nova project set project-1

      /me Selected Openstack project: project-1 for some-user@chat.hipchat.com

Errbot will remember your selection. You can change your selection at any time by repeating the above steps.


Contributing
------------

1. Fork this repository on Github
2. Create a named feature branch (like `add_component_x`)
3. Write your change
4. Submit a Pull Request

License
-------
GNU General Public License
