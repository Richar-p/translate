# -*- coding: utf-8 -*-
#
# Copyright 2008,2011 Zuza Software Foundation
#
# This file is part of translate.
#
# translate is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# translate is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

# Original Author: Dan Schafer <dschafer@mozilla.com>
# Date: 10 Jun 2008

"""Convert Gettext PO localization files to Mozilla .lang files.
"""

from translate.convert import convert
from translate.storage import mozilla_lang, po


class po2lang(object):
    """Convert a PO file to a Mozilla .lang file."""

    SourceStoreClass = po.pofile
    TargetStoreClass = mozilla_lang.LangStore

    def __init__(self, input_file, include_fuzzy=False, output_threshold=None,
                 mark_active=True):
        """Initialize the converter."""
        self.source_store = self.SourceStoreClass(input_file)

        self.should_output_store = convert.should_output_store(
            self.source_store, output_threshold
        )
        if self.should_output_store:
            self.include_fuzzy = include_fuzzy

            self.target_store = self.TargetStoreClass(mark_active=mark_active)

    def convert_store(self):
        """Convert a single source format file to a target format file."""
        for source_unit in self.source_store.units:
            if source_unit.isheader() or not source_unit.istranslatable():
                continue
            target_unit = self.target_store.addsourceunit(source_unit.source)
            if self.include_fuzzy or not source_unit.isfuzzy():
                target_unit.target = source_unit.target
            else:
                target_unit.target = ""
            if source_unit.getnotes('developer'):
                target_unit.addnote(source_unit.getnotes('developer'), 'developer')
        return self.target_store


def run_converter(inputfile, outputfile, templatefile=None, includefuzzy=False,
                  mark_active=True, outputthreshold=None):
    """Wrapper around converter."""
    convertor = po2lang(inputfile, includefuzzy, outputthreshold, mark_active)

    if not convertor.should_output_store:
        return 0

    if convertor.source_store.isempty():
        return 0

    outputstore = convertor.convert_store()
    outputstore.serialize(outputfile)
    return 1


formats = {
    "po": ("lang", run_converter),
    ("po", "lang"): ("lang", run_converter),
}


def main(argv=None):
    parser = convert.ConvertOptionParser(formats, usetemplates=True,
                                         description=__doc__)
    parser.add_option(
        "", "--mark-active", dest="mark_active", default=False,
        action="store_true", help="mark the file as active")
    parser.add_threshold_option()
    parser.add_fuzzy_option()
    parser.passthrough.append("mark_active")
    parser.run(argv)


if __name__ == '__main__':
    main()
