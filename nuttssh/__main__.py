# Nuttssh - Copyright Matthijs Kooijman <matthijs@stdin.nl>
#
# This file is made available under the MIT license. See the accompanying
# LICENSE file for the full text.

import sys
import asyncio
import logging

from . import server


def main():
    """Main entry point, which runs a nuttssh server."""
    # http://asyncssh.readthedocs.io/en/latest/api.html#asyncssh.set_debug_level
    # asyncssh.set_debug_level(3)
    try:
        logging.basicConfig(level=logging.DEBUG)

        # Start up the daemon
        loop = asyncio.get_event_loop()
        daemon = server.NuttsshDaemon()
        loop.run_until_complete(daemon.start())
    except Exception as exc:
        sys.exit('Error starting server: ' + str(exc))

    # Keep running until all async stuff is finished
    loop.run_forever()


# This file is called by python's -m option, so run the main function in that
# case
main()
