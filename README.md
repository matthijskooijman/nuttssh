Nuttssh - SSH-based virtual tunnel switchboard server
=====================================================
Nuttssh is a small Python-based SSH server that internally connects forwarded
ports between different SSH clients. It was designed to work as a way to
connect to machines running behind a NAT, by letting them initiate an outgoing
SSH connection and then piggy-back a reverse SSH connection to access the
machine. When used like that, Nuttssh acts somewhat as a very lightweight VPN
server.

More generally, nuttsh can be used to let SSH clients request opening a
listening port, which results in an internal virtual port being opened (no
actual TCP ports on the server are opened). Then another SSH client can request
to connect to that listening port, using a configurable name to identify the
client whose port to connect to.

This works very similar to using a normal SSH server with port forwarding,
except that when using Nuttssh:
 - Not actual TCP ports are opened on the server.
 - Clients do not need to actually authenticate as a system user, Nuttssh
   handles its own key authentication.
 - When multiple clients request a listening port, they can use the same port
   number, since their hostname will be used to select the right one. This
   removes the need to ensure that each listening client chooses a unique port
   number.
 - When connecting to a listening port, a hostname and the regular port number
   (e.g. 22 for SSH) can be used, rather than having to keep track of which
   port number maps to which client.

To circumvent the downsides of normal SSH port forwarding (in particular the
last two), Nuttssh was created. It replaces the central server, while still
allowing normal SSH clients to be used.

Nuttssh still young, but should be usable already. There is still plenty of
room for improvement, especially with regard to configurability.

## Terminology
 - (Nuttssh) server: The central server that accepts connections from various
   clients, and connects them together.
 - Listening client: A client that connects to the Nuttssh server and requests
   listening ports. This is *not* called a "listener", to prevent confusing
   with the `SSHListener` class used in AsyncSSH.
 - Initiating client or initiator: A client that connects to the Nuttssh server
   and requests a connection to a listening client.
 - Circuit: the virtual connection between two clients through the Nuttssh
   server. Called a circuit to disambiguate from the normal connection between
   the client and the Nuttssh server.

   Note that a client is typically either listening or initiating, but given
   sufficient permissions,  a client could also act as both.

The above terminology is not used everywhere yet, in some cases a listening
client is called a slave and an initiating client is called a master (coming
from the original usecase of remote control).

## Installing / running
The easiest way to run Nuttsh is to install it using pip. E.g.:

    pip3 install nuttsh

Optionally add `--user` to install for your user only (without
requiring root), or run inside an activated virtualenv.

Then, to run the nuttsh server:

    python3 -m nuttsh

Alternatively, you can also clone this repository, and run `python3 -m nuttsh`
from the root of the repository, without requiring installation.

Note that this uses `pip3` and `python3` to get the Python 3 versions. If this
is the default on your system (or you are using from a virtualenv containing
Python 3), you might also be able to just use `pip` and `python` instead.

## Configuration
Currently, no configuration file or options is supported. There are some
constants in the top of `nuttssh/server.py` that hardcode nuttsh to listen on
any interface, on port 2222 and set the name of the `ssh_host_key` and
`authorized_keys` file.

### SSH host key
To allow starting `nuttssh`, an ssh host key must be present. This should be
put into a file called `ssh_host_key` in the current directory. To generate one
using OpenSSH's `ssh-keygen`, run:

    ssh-keygen -t rsa -b 2048 -P "" -f ssh_host_key

This generates a 2048-bit RSA key without a passphrase.

### Access control
To control access to the nuttsh server, an `authorized_keys` file must be
present (without it, nuttsh will refuse to start). This file uses the same
format as OpenSSH's `authorized_keys` file. Each line must contain a single
public key (copied from e.g. the `id_rsa.pub` file). In front of the public
key, options can be added.

For example, a file could look like this (keys are truncated for the example):

    access="listen" ssh-rsa AAAAB3NzaC1yc2EAAAADAJnmVYPYe94v user@host
    access="listen",access="initiate",from="192.168.1.0/24" ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAA+ user@host

This consists of a comma-separated list of options, a keytype, the actual key
and a comment.

Currently, the following options are supported:
 - `access` to specify the permissions for the client. Supported values are
   `listen` (to allow opening listening ports) and `initiate` (to allow
   connecting to listening ports). This option can be specified more than once,
   to give more than one type of permission.
 - `from` to limit connections to specific hosts. The value is a
   comma-separated list of patterns. Each pattern can be a glob pattern (using
   `*` and `?`, e.g.  `"*.mydomain.tld"`) matched against the address and
   hostname, or a CIDR-style address and mask (e.g.  `"192.168.1.0/24"`). A
   connection is allowed if it matches at least one of the patterns in the
   list. This option can be specified multiple times, in which case a
   connection must match (one element of) each `from` option separately.

   See the OpenSSH `authorized_keys` manpage for more info on this option.
 - `hostname` and `alias` allow configuring the name(s) that can be used to
   connect to this client. See below for details.

Note that when a client has multiple keys, the first one offered by the client
that is present in the `authorized_keys` file is used, even when another is
also present and has more permissions or other options.

### Slave hostnames and aliases
Each connected client has a hostname, and an optional list of alias names. The
hostname is used in various places to refer to a client, while both the
hostname and the aliases can be used to select a listening client to connect
to.

By default, the username specified by the client is used as its hostname (this
looks a bit like a hack, but it seems like the cleanest approach). Using the
`hostname` option in `authorized_keys`, this hostname can be overridden for a
given connection. Using the `alias` option, additional alias names can be
specified (the option must be specified multiple times for multiple aliases).

When multiple connections each claim the same name (hostname or alias), only
the first client to connect can actually be reached using that name. Once that
client disconnects, the next one will become reachable again.

### Connecting listening clients
Connections to the Nuttssh server use the normal SSH protocol, so can use a
regular SSH client. To open up a listening port, the normal port forwarding
options can be used. For example:

    ssh myhost@nuttsh.example.org -p 2222 -R 22:localhost:22 -N

This connects to a Nuttssh server running on `nuttsh.example.org`, port 2222.
Our hostname (`myhost`) is passed as the username.  No shell or other remote
command is run (`-N`), but a (virtual) port 22 is opened in the Nuttssh server.
Any incoming circuits on that port are forwarded through the SSH connection and
connected to localhost:22 (in other words, our local port 22 is exposed through
Nuttssh).

Typically you want a listening client to be continuously connected (and
reconnect on errors). This is easy using `autossh`, just replace `ssh` with
`autossh`, and that will take care of autoconnecting.

By default, `autossh` uses additional port forwards to test connectivity, which
do not work with Nuttssh so these should be disabled in favor of letting SSH
itself do keepalive. Additionally, when running unattended, `autossh` should be
told to always keep retrying, even on startup errors.

#### Changing port numbers
The above examples all assume that the listening clients requests a listening
port 22 and forwards any incoming circuits to `localhost:22`, which is probably
the common case. However, it is also possible to forward to a different local
host or port by specifying them with the `-R` option.

For example:

    ssh myhost@nuttsh.example.org -p 2222 -R 80:localhost:8080 -N

This requests a virtual port 80 on the Nuttssh server and connects any incoming
circuits to port 8080 on localhost. Note that this is completely invisible to
the initiating clients, since these only need to specify the hostname
(`myhost`) and virtual listening port (80).

### Connecting initiating clients
Initiating clients also use the plain SSH protocol and can use a normal SSH
client. For example, to set up an SSH connection to the listening client from
the previous example, using a circuit through the NuttSSH server:

    ssh -J nuttsh.example.org:2222 myhost

This instructs ssh to first connect to `nuttssh.example.org`, port 2222 and
then inside that connection, ask the Nuttssh server to set up a circuit
(tunneled connection) to `myhost`, port 22 (not specified explicitly). This
hostname and port combination is then matched by the Nuttsh server to the
previously connected listening client and the circuit is routed to that client.
Finally, the listening client then completes the circuit by locally connecting
to its own SSH port, as requested by the `localhost:22` part in its `-R`
option.

This makes use of the SSH `-J` option, using the Nuttssh as a *jump host*. This
is convenient for routing SSH connections through a circuit, but does not work
for other kinds of connections. Fortunately, ssh allows other ways to set up
these circuit connections as well.

Note that this makes two SSH connections, one to the Nuttsh server and one to
the listening client. This also means that authentication must happen twice.

#### Forwarding local ports through a circuit
You can also ask SSH to open a local listening port, and create a circuit for
each incoming connection on that port. For example:

    ssh -L 22:myhost:22 nuttsh.example.org -p 2222 -N

Opens up port 22 locally, and forwards any connections through a circuit to
port 22 on `myhost`. Again `-N` is specified to prevent trying to execute a
remote shell or command.

Note that more than one circuit can be created in this way, each of which will
be routed through the same SSH connection to the Nuttssh server.

#### Forwarding stdin/stdout through a circuit
SSH can also forward data on its stdin and stdout streams into a circuit. For
example:

    ssh -W myhost:22 nuttsh.example.org -p 2222

This opens a circuit to `myhost` on port 22, and connects it to the stdin and
stdout of the local ssh client. The `-N` option is implied by `-W`, so does
need to be separately specified.

#### Routing a SOCKS proxy requests through a circuit
SSH supports exposing a SOCKS proxy. This proxy is implemented completely in
the local SSH client, and allows (local) programs, such as a webbrowser, to
route all of their traffic through the proxy. In this case, this means all
connections will be made through circuits (and thus connections can be made to
all listening hosts, but not other hosts).

To set this up, run:

    ssh -D 3128 nuttsh.example.org -p 2222 -N

This instructs ssh to open up a SOCKS proxy port on local port 3128, which can
then be used by other programs.

Note that this setup requires the client to support SOCKS v5 and do name
resolution through the proxy (e.g. Firefox has a "Proxy DNS when using SOCKS
v5" optoin for this). Without this (and with SOCKS v4), names are locally
resolved (which will fail) and only the resulting IP address is included in the
proxy request.

### Using ssh config files
All of the above mentioned ssh options (except `-N` it seems) can also be
configured through SSH configuration file options, so you can define some
presets and apply them by just passing a hostname to ssh. See the `ssh_config`
manpage for more info.

# Contributing
This is an open project, and contributions are welcomed. For bug reports,
feature suggestions and questions, please use the github issue tracker. To
contribute patches, use github pull requests.

When contributing patches, make sure to provide good quality contributions. In
particular, code style should be consistent, commits should be cleanly
separated with a single logical change per commit and commit messages should be
clear. In other words, make sure the code and commit history is easy to read
and review. Additionally, please explicitly state that you make your
patch available under the MIT license.

To check the coding style of the code, the flake8 tool is used. As a
convenience, a `Makefile` is provided that allows running `make check` to run
all checks (currently only flake8). This should not return any errors after any
commit, so make sure to run it regularly. To fix import sorting errors, run
`make sort`.

# License (also setup.py)
Nuttssh was written by Matthijs Kooijman. Its sources, as well as the
accompanying documentation and other files in this repository are available
under the MIT license. See the [`LICENSE`](LICENSE) file for the full license text.

# About Nuttssh
Nuttssh was originally created for the [Meetjestad!](http://www.meetjestad.net)
project, to provide lightweight remote control for LoRa gateways spread
throughout the city on varying internet connections (usually not publically
reachable due to NAT). After some initial experiments with a reverse SSH
connection and SSH channel multiplexing (which worked, but resulted in fragile
code), the current approach of using port forwards was implemented. For this,
some inspiration was taking from
[ssh-proxy](https://github.com/luke-jr/ssh-proxy), which also uses remote port
forwarding (but uses key fingerprints to identify clients, and probably
predates the SSH "jump host" feature).

Since how Nuttssh works seems a bit similar to the way telephone switchboards
used to work years ago, Nuttssh is named after Emma & TODO Nutt, which were the
first two female telephone switchboard operators. The name "circuit" is also
taken from telephone jargon.
