# Nuttssh - Copyright Matthijs Kooijman <matthijs@stdin.nl>
#
# This file is made available under the MIT license. See the accompanying
# LICENSE file for the full text.
#
# This file handles commands that can be executed through SSH, to inspect and
# administrate the server.

from .server import Permissions


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
    # TODO: Properly implement command parsing, using e.g. click. For now, just
    # always run the list command
    list(server, process)


def list(server, process):
    """List all active listeners."""
    # TODO: Put this in a decorator?
    if Permissions.LIST_LISTENERS not in server.permissions:
        process.stderr.write("Permission denied\n")
        process.exit(1)
        return

    process.stdout.write("Listening clients:\n")
    # TODO: We should probably just keep a list of server instances, or perhaps
    # structure this output differently.
    servers = {s for ss in server.daemon.listener_names.values() for s in ss}

    if servers:
        for s in sorted(servers, key=lambda x: x.hostname):
            peername = s.conn.get_extra_info('peername')
            ip = peername[0]
            ports = (l.listen_port for l in s.listeners.values())

            process.stdout.write("  {}: ip={} aliases={} ports={}\n".format(
                s.hostname,
                ip,
                ','.join(s.aliases),
                ','.join(str(p) for p in sorted(ports)),
            ))
    else:
        process.stdout.write("  None\n")
    process.exit(0)
