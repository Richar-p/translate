#
# Copyright 2008-2009 Zuza Software Foundation
#
# This file is part of translate.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

"""Wrapper to launch the bundled CherryPy server."""

import logging

from cheroot.wsgi import Server

logger = logging.getLogger(__name__)


def launch_server(host, port, app, **kwargs):
    """Use cheroot WSGI server, a multithreaded scallable server."""
    server = Server((host, port), app, **kwargs)
    logger.info("Starting server, listening on port %s", port)
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
