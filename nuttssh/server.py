# Nuttssh - Copyright Matthijs Kooijman <matthijs@stdin.nl>
#
# This file is made available under the MIT license. See the accompanying
# LICENSE file for the full text.
#
# This file handle the main SSH server, authentication and creation of
# circuits.

import enum
import logging
import collections

import asyncssh

from . import util

LISTEN_HOST = '0.0.0.0'
LISTEN_PORT = 1878
HOST_KEY_FILE = 'ssh_host_key'
KEYS_FILE = 'authorized_keys'


class Permissions(enum.Enum):
    # Open (virtual) ports for listening
    LISTEN = 1
    # Connecting to (virtual) ports
    INITIATE = 2
    # Connecting to (virtual) ports
    LIST_LISTENERS = 3


"""
Predefined access levels, mapping to a more fine-grained list of permissions.
"""
access_levels = {
    'listen': {Permissions.LISTEN},
    'initiate': {Permissions.INITIATE, Permissions.LIST_LISTENERS},
}


class NuttsshDaemon:
    """Daemon that listens on a port and serves multiple connections."""

    def __init__(self):
        # Maps listening names to NutsshServers listening on that name
        self.listener_names = collections.defaultdict(list)

    async def start(self):
        """
        Aysynchronously start the SSH server, and process connections.

        This server will listen on the configured host and port.
        """
        def server_factory():
            return NuttsshServer(self)

        # Callable that is called to handle shell or command execution requests
        # (note that this does not build a SSHServerProcess object, it just
        # accepts an existing one and handle the execution of the task).
        # It is is a bit smelly that this is a global factory function rather
        # than being a callback on the server object, but with the
        # session_requested callback that can be called by
        # SSHServerConnection._process_session_open(), it only creates a
        # SSHServerStreamSession, not a SSHServerProcess that we need (and the
        # SSHServerProcess constructro is not public/stable API).
        # So this global function just looks up the server and delegates to it.
        async def process_factory(process):
            # This extra info must be set by the server object, there is no
            # (documented) way to get the server from the process object
            server = process.channel.get_extra_info('server')
            await server.handle_command_or_shell(process)

        await asyncssh.listen(
            LISTEN_HOST, LISTEN_PORT,
            reuse_address=True,
            server_host_keys=[HOST_KEY_FILE],
            server_factory=server_factory,
            process_factory=process_factory,
        )


class NuttsshServer(asyncssh.SSHServer):
    """
    SSHServer class that serves a single connection.

    This is created by asyncssh on each incoming connections and its methods
    are called to decide how to handle incoming requests.
    """

    def __init__(self, daemon):
        self.daemon = daemon
        # Maps ports to SlaveListener objects
        self.listeners = {}
        self.username = None
        # Primary name
        self.hostname = None
        # Additional names
        self.aliases = []
        # All names
        self.names = []
        self.permissions = set()
        self.authorized_keys = None

    def connection_made(self, conn):
        """Called when the connection is opened."""
        self.conn = conn
        # For NuttsshDaemon.start.process_factory
        conn.set_extra_info(server=self)
        logging.info('Connection received from %s',
                     conn.get_extra_info('peername')[0])

    def connection_lost(self, exc):
        """Called when the connection is lost."""
        if exc:
            logging.error('Connection error: %s', str(exc))
        else:
            logging.info('Connection closed.')

        # Clean up (just in case, all listeners should have been closed and
        # removed themselves already)
        for listener in self.listeners:
            listener.close()

    def validate_public_key(self, username, key):
        """
        Called when the client presents a key for authentication if lookup
        in authorized_keys failed.
        """

        # Looking up keys is handled by the connection already, but overriding
        # this hook allows logging failed keys.
        keystr = key.export_public_key().decode().strip()

        logging.debug("Rejecting key %s %s", keystr, username)
        return False

    def auth_completed(self):
        """Process the options of the accepted key."""
        access = self.conn.get_key_option('access', [])
        if not access:
            # TODO: Should this disconnect, or skip this key?
            logging.warning("Used key has no access level")

        self.permissions = set()
        for level in access:
            try:
                self.permissions |= access_levels[level]
            except KeyError:
                logging.error("Key has unknown access level: \"%s\"", level)

        # If not specified in the key options, assume that the hostname is the
        # hostname.
        username = self.conn.get_extra_info('username')
        hostnames = self.conn.get_key_option('hostname', [username])
        if len(hostnames) > 1:
            logging.warning("Multiple hostnames specified, using the first")
        self.hostname = hostnames[0]
        self.aliases = self.conn.get_key_option('alias', [])
        self.names = [self.hostname] + self.aliases

    def begin_auth(self, username):
        """The client has started authentication with the given username."""
        try:
            authorized_keys = asyncssh.read_authorized_keys(KEYS_FILE)
        except Exception as e:
            # No point in continuing without authorized keys
            logging.error("Failed to read key file: %s", e)
            raise asyncssh.DisconnectError(
                asyncssh.DISC_NO_MORE_AUTH_METHODS_AVAILABLE,
                "Invalid server configuration", "en")
        self.conn.set_authorized_keys(authorized_keys)

        # Auth required
        return True

    def server_requested(self, listen_host, listen_port):
        """The client requested us to open a listening port."""
        if Permissions.LISTEN not in self.permissions:
            logging.error("No LISTEN permission, denying request")
            return False

        # We do not support dynamic ports
        if listen_port == 0:
            logging.error("Dynamic listen port not supported, denying request")
            return False

        # TODO: Should we require listen_host to be "localhost"? That matches
        # the semantics of our "virtual listener" structure best?

        logging.info("Creating virtual listener for %s, port %s",
                     self.names, listen_port)

        return self.create_listener(listen_host, listen_port)

    def connection_requested(self, dest_host, dest_port, orig_host, orig_port):
        """
        The client requested us to make a connection to a given host and port.

        The original host and port indicate the source of the connection on
        client side (but are irrelevant here).
        """
        if Permissions.INITIATE not in self.permissions:
            logging.error("No INITIATE permission, denying request")
            raise asyncssh.ChannelOpenError(
                asyncssh.SSH_OPEN_ADMINISTRATIVELY_PROHIBITED,
                "Insufficient permissions to connect", "en")
        return self.connect_to_slave(dest_host, dest_port)

    async def handle_command_or_shell(self, process):
        """
        Called by NuttsshDaemon.start.process_factory when a shell or command
        execution is requested by the client.
        """
        # TODO: Move upwards, but that introduces a circular dependency
        from . import commands

        commands.handle_command(self, process, process.command)

    def create_listener(self, host, port):
        """Create and register a new listener."""
        # If this is the first, prepend ourselves to the list of listening
        # names
        if not self.listeners:
            for name in self.names:
                self.daemon.listener_names[name].insert(0, self)

        if port in self.listeners:
            logging.error("Duplicate listen port %s requested, refusing the"
                          "second one", port)
            return False

        # This remembers listen_host so we can tell the client what listener is
        # being used, but it is otherwise ignored.
        listener = VirtualListener(self, host, port)

        self.listeners[port] = listener

        return listener

    def remove_listener(self, listener, port):
        """
        Remove a listener.

        Should only be called from VirtualListener.close()
        """
        del self.listeners[port]

        # If the last listener was closed, unregister our names
        if not self.listeners:
            for name in self.names:
                self.daemon.listener_names[name].remove(self)

        logging.info("Removed virtual listener for %s, port %s",
                     self.names, port)

    async def connect_to_slave(self, host, port):
        # Split off any index from the name, defaulting to the most recent
        # client (index 0)
        name, index = util.split_hostname_index(host, 0)

        # Find the slave
        slaves = self.daemon.listener_names[name]
        if not slaves:
            logging.error("Slave %s not found", name)
            raise asyncssh.ChannelOpenError(
                asyncssh.OPEN_CONNECT_FAILED,
                "Slave %s not found" % (name,), "en")

        try:
            slave = slaves[index]
        except IndexError:
            logging.error("Invalid index %s for slave %s", index, name)
            raise asyncssh.ChannelOpenError(
                asyncssh.OPEN_CONNECT_FAILED,
                "Invalid index %s for slave %s" % (index, name), "en")

        # Find the port
        logging.debug("%s", slave.listeners)
        listener = slave.listeners.get(port, None)
        if not listener:
            logging.error("Port %s on slave %s not found",
                          port, slave.hostname)
            raise asyncssh.ChannelOpenError(
                asyncssh.OPEN_CONNECT_FAILED,
                "Port %s on slave %s not found" % (port, slave.hostname),
                "en")

        # This creates a connection back to the slave that requested the port
        # forward (using the listener). It uses two instances of the
        # SSHForwarder class to forward data between this slave connection and
        # the requested incoming connection.
        # TODO: SSHForwarder is not documented as a public API. Should we use
        # it?
        peer_factory = asyncssh.forward.SSHForwarder
        _, conn = await listener.create_connection(peer_factory)
        return asyncssh.forward.SSHForwarder(conn)


class VirtualListener(asyncssh.SSHListener):
    """
    Represents the server side of a listening port opened by a client.

    This class mostly serves as a way to trick open listening ports, and allows
    asyncssh to close existing listeners (on client request, or when the
    connection is closed). Additionally, this class handles creating new
    tunneled connections to the client when an (virtual) connection to the
    listening port is made.
    """

    def __init__(self, server, listen_host, listen_port):
        self.server = server
        self.listen_host = listen_host
        self.listen_port = listen_port

    async def create_connection(self, peer_factory):
        """
        Create a new tunneled connection to the underlying client.

        This looks to the client like an incoming connection on the listening
        port.

        This works similar to asyncio.create_connection: The peer_factory will
        be passed the created connection and should return the peer, and when
        data comes in on the connection it is passed to the data_received
        method on the peer.
        """
        # This passes the original listen host and port, so the client knows
        # which port forward this connection belongs to
        return await self.server.conn.create_connection(
            peer_factory, self.listen_host, self.listen_port,
        )

    def close(self):
        """
        Close this listener.

        Called when the client cancels it, or the connection is closed.
        """
        self.server.remove_listener(self, self.listen_port)

    async def wait_close(self):
        """Wait for all listeners to be closed."""
        # Since closing is synchronous, no need to wait here.
        pass
