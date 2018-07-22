# Nuttssh - Copyright Matthijs Kooijman <matthijs@stdin.nl>
#
# This file is made available under the MIT license. See the accompanying
# LICENSE file for the full text.
#
# This file handles commands that can be executed through SSH, to inspect and
# administrate the server.


def handle_command(server, process, command):
    """
    Parse and handle a single command from a client.

    This is the main entry point for the commands module.

    :param server: The NuttsshServer object for the current connection.
    :param process: The SSHServerProcess object created by AsyncSSH for this
                    command channel.
    :param command: The command to execute. This is either the string passed by
                    the SSH client, or None when no command was passed (and a
                    shell was requested).
    """
    # TODO
    process.exit(1)
