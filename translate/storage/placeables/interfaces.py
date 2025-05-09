#
# Copyright 2009 Zuza Software Foundation
#
# This file is part of the Translate Toolkit.
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

"""
This file contains abstract (semantic) interfaces for placeable
 implementations.
"""

from __future__ import annotations

from typing import Callable

from translate.storage.placeables.strelem import StringElem


class BasePlaceable(StringElem):
    """Base class for all placeables."""

    parse: Callable[[str], list[StringElem]]


class InvisiblePlaceable(BasePlaceable):
    pass


class MaskingPlaceable(BasePlaceable):
    pass


class ReplacementPlaceable(BasePlaceable):
    pass


class SubflowPlaceable(BasePlaceable):
    pass


class Delimiter:
    pass


class PairedDelimiter:
    pass
