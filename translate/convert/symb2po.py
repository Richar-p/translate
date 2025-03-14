#
# Copyright 2008-2009 Zuza Software Foundation
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
Convert Symbian localisation files to Gettext PO localization files.

See: http://docs.translatehouse.org/projects/translate-toolkit/en/latest/commands/symb2po.html
for examples and usage instructions.
"""

from translate.storage import factory
from translate.storage.pypo import unescape
from translate.storage.symbian import (
    ParseState,
    eat_whitespace,
    header_item_or_end_re,
    header_item_re,
    identity,
    read_charset,
    read_while,
    skip_no_translate,
    string_entry_re,
)


def read_header_items(ps):
    match = read_while(ps, header_item_or_end_re.match, lambda match: match is None)
    if match.groupdict()["end_comment"] is not None:
        return {}

    results = {}
    while match:
        match_chunks = match.groupdict()
        ps.read_line()
        results[match_chunks["key"]] = match_chunks["value"]
        match = header_item_re.match(ps.current_line)

    match = read_while(ps, identity, lambda line: not line.startswith("*/"))
    ps.read_line()
    return results


def parse(ps):
    header = read_header_items(ps)
    units = []
    try:
        while True:
            eat_whitespace(ps)
            skip_no_translate(ps)
            match = string_entry_re.match(ps.current_line)
            if match is not None:
                units.append(
                    (match.groupdict()["id"], unescape(match.groupdict()["str"][1:-1]))
                )
            ps.read_line()
    except StopIteration:
        pass
    return header, units


def read_symbian(f):
    lines = list(f)
    charset = read_charset(lines)
    return parse(ParseState(iter(lines), charset))


def get_template_dict(template_file):
    if template_file is not None:
        template_header, template_units = read_symbian(template_file)
        return template_header, dict(template_units)
    return {}, {}


def build_output(units, template_header, template_dict):
    output_store = factory.classes["po"]()
    ignore = {"r_string_languagegroup_name"}
    header_entries = {
        "Last-Translator": template_header.get("Author", ""),
        "Language-Team": template_dict.get("r_string_languagegroup_name", ""),
        "Content-Transfer-Encoding": "8bit",
        "Content-Type": "text/plain; charset=UTF-8",
    }
    output_store.updateheader(add=True, **header_entries)
    for id, source in units:
        if id in ignore:
            continue
        unit = output_store.UnitClass(source)
        unit.target = template_dict.get(id, "")
        unit.addlocation(id)
        output_store.addunit(unit)
    return output_store


def convert_symbian(
    input_file, output_file, template_file, pot=False, duplicatestyle="msgctxt"
):
    _header, units = read_symbian(input_file)
    template_header, template_dict = get_template_dict(template_file)
    output_store = build_output(units, template_header, template_dict)

    if output_store.isempty():
        return 0
    output_store.serialize(output_file)
    return 1


def main(argv=None):
    from translate.convert import convert

    formats = {"r01": ("po", convert_symbian)}
    parser = convert.ConvertOptionParser(
        formats, usetemplates=True, usepots=True, description=__doc__
    )
    parser.add_duplicates_option()
    parser.passthrough.append("pot")
    parser.run(argv)


if __name__ == "__main__":
    main()
