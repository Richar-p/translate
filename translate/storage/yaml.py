#
# Copyright 2016 Michal Čihař
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

r"""Class that manages YAML data files for translation."""

import uuid

from ruamel.yaml import YAML, YAMLError
from ruamel.yaml.comments import CommentedMap, TaggedScalar

from translate.lang.data import cldr_plural_categories
from translate.storage import base


class YAMLUnitId(base.UnitId):
    KEY_SEPARATOR = "->"
    INDEX_SEPARATOR = "->"

    def __str__(self):
        result = super().__str__()
        # Strip leading ->
        if result.startswith(self.KEY_SEPARATOR):
            return result[len(self.KEY_SEPARATOR) :]
        return result


class YAMLUnit(base.DictUnit):
    """A YAML entry."""

    IdClass = YAMLUnitId

    def __init__(self, source=None, **kwargs):
        # Ensure we have ID (for serialization)
        if source:
            self.source = source
            if isinstance(source, dict):
                self._id = hex(
                    hash(str(source))
                )  # ✅ Convert dict to a hashable string
            else:
                self._id = hex(hash(source))
        else:
            self._id = str(uuid.uuid4())
        super().__init__(source)

    @property
    def source(self):
        return self.target

    @source.setter
    def source(self, source):
        self.target = source

    def getid(self):
        return self._id

    def getlocations(self):
        return [self.getid()]

    def convert_target(self):
        return self.target

    def storevalues(self, output):
        self.storevalue(output, self.convert_target())


class YAMLFile(base.DictStore):
    """A YAML file."""

    UnitClass = YAMLUnit

    def __init__(self, inputfile=None, **kwargs):
        """Construct a YAML file, optionally reading in from inputfile."""
        super().__init__(**kwargs)
        self.filename = ""
        self._original = self.get_root_node()
        self.dump_args = {
            "default_flow_style": False,
            "preserve_quotes": True,
        }
        if inputfile is not None:
            self.parse(inputfile)

    def get_root_node(self):
        """Returns root node for serialize."""
        return CommentedMap()

    @property
    def yaml(self):
        yaml = YAML()
        for arg, value in self.dump_args.items():
            setattr(yaml, arg, value)
        return yaml

    def serialize(self, out):
        # Always start with valid root even if original file was empty
        if self._original is None:
            self._original = self.get_root_node()

        units = self.preprocess(self._original)
        self.serialize_units(units)
        self.yaml.dump(self._original, out)

    def _parse_dict(self, data, prev):
        # Avoid using merged items, it is enough to have them once
        for k, v in data.non_merged_items():
            yield from self._flatten(v, prev.extend("key", k))

    def _flatten(self, data, prev=None):
        """Flatten YAML dictionary."""
        if prev is None:
            prev = self.UnitClass.IdClass([])
        if isinstance(data, dict):
            yield from self._parse_dict(data, prev)
        elif isinstance(data, str):
            yield (prev, data)
        elif isinstance(data, (bool, int)):
            yield (prev, str(data))
        elif isinstance(data, list):
            for k, v in enumerate(data):
                yield from self._flatten(v, prev.extend("index", k))
        elif isinstance(data, TaggedScalar):
            yield (prev, data.value)
        elif data is None:
            pass
        else:
            raise ValueError(
                "We don't handle these values:\n"
                f"Type: {type(data)}\n"
                f"Data: {data}\n"
                f"Previous: {prev}"
            )

    @staticmethod
    def preprocess(data):
        """Preprocess hook for child formats."""
        return data

    def parse(self, input):
        """Parse the given file or file source string."""
        if hasattr(input, "name"):
            self.filename = input.name
        elif not getattr(self, "filename", ""):
            self.filename = ""
        if hasattr(input, "read"):
            src = input.read()
            input.close()
            input = src
        if isinstance(input, bytes):
            input = input.decode("utf-8")
        try:
            self._original = self.yaml.load(input)
        except YAMLError as e:
            message = getattr(e, "problem", getattr(e, "message", str(e)))
            if hasattr(e, "problem_mark"):
                message += f" {e.problem_mark}"
            raise base.ParseError(message)

        content = self.preprocess(self._original)

        for k, data in self._flatten(content):
            unit = self.UnitClass(data)
            unit.set_unitid(k)
            self.addunit(unit)

    def removeunit(self, unit):
        if self._original is not None:
            units = self.preprocess(self._original)
            unit.storevalue(units, None, unset=True)
        super().removeunit(unit)


class RubyYAMLUnit(YAMLUnit):
    def convert_target(self):
        """Ensure plural messages are stored as a single unit."""
        if isinstance(self.target, dict) and all(
            k in cldr_plural_categories for k in self.target
        ):
            return CommentedMap(self.target)  # ✅ Safely convert plurals

        return self.target  # ✅ Return normally for non-plurals


class RubyYAMLFile(YAMLFile):
    """Ruby YAML file, it has language code as first node."""

    UnitClass = RubyYAMLUnit

    def preprocess(self, data):
        if isinstance(data, CommentedMap) and len(data) == 1:
            lang = next(iter(data.keys()))
            # Handle blank values
            if data[lang] is None:
                data[lang] = CommentedMap()
            # Do not try to parse string only, CommentedMap is dict as well
            if isinstance(data[lang], dict):
                self.settargetlanguage(lang)
                return data[lang]
        return data

    def get_root_node(self):
        """Returns root node for serialize."""
        result = CommentedMap()
        result[self.targetlanguage or "en"] = CommentedMap()
        return result

    def _parse_dict(self, data, prev):
        """Ensure plurals are stored as a single unit and handle partial blanks properly."""
        if isinstance(data, dict):
            plural_keys = [k for k in data if k in cldr_plural_categories]

            # ✅ If all plural categories are present but some are empty, we still need the unit
            if plural_keys and len(plural_keys) == len(data):
                if any(v is not None for v in data.values()):
                    # At least one non-empty value, so create a unit
                    yield (
                        prev,
                        {k: data[k] for k in cldr_plural_categories if k in data},
                    )
                else:
                    # If all are empty or None, skip creating a unit
                    return
            else:
                # If it's not a complete plural group, proceed normally
                yield from super()._parse_dict(data, prev)
        else:
            # Normal case for non-dictionaries
            yield from super()._parse_dict(data, prev)

    def serialize(self, out):
        # Always start with valid root even if original file was empty
        if self._original is None:
            self._original = self.get_root_node()

        units = self.preprocess(self._original)
        self.serialize_units(units)

        # Ensure the correct order is maintained before serialization
        self._original = self.reorder_plural_categories(self._original)

        self.yaml.dump(self._original, out)

    def reorder_plural_categories(self, data):
        """Reorders the plural categories to match cldr_plural_categories."""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict) and all(
                    k in cldr_plural_categories for k in value
                ):
                    # Reorder the keys in the dictionary to match cldr_plural_categories
                    ordered = {
                        key: value[key]
                        for key in cldr_plural_categories
                        if key in value
                    }
                    data[key] = CommentedMap(ordered)
                else:
                    # Recursively reorder nested dictionaries
                    self.reorder_plural_categories(value)
        return data
