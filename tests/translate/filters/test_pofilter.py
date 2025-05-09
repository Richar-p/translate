from io import BytesIO

from translate.filters import checks, pofilter
from translate.storage import factory, xliff

from ..storage.test_base import first_translatable, headerless_len


class BaseTestFilter:
    """Base class for filter tests."""

    filename = ""

    def parse_text(self, filetext):
        """Helper that parses xliff file content without requiring files."""
        dummyfile = BytesIO(filetext.encode())
        dummyfile.name = self.filename
        return factory.getobject(dummyfile)

    def filter(self, translationstore, checkerconfig=None, cmdlineoptions=None):
        """
        Helper that passes a translations store through a filter, and
        returns the resulting store.
        """
        if cmdlineoptions is None:
            cmdlineoptions = []
        options, _args = pofilter.cmdlineparser().parse_args(
            [self.filename, *cmdlineoptions]
        )
        checkerclasses = [checks.StandardChecker, checks.StandardUnitChecker]
        if checkerconfig is None:
            parser = pofilter.FilterOptionParser({})
            checkerconfig = parser.build_checkerconfig(options)
        checkfilter = pofilter.pocheckfilter(options, checkerclasses, checkerconfig)
        return checkfilter.filterfile(translationstore)

    def test_simplepass(self):
        """Checks that an obviously correct string passes."""
        filter_result = self.filter(self.translationstore)
        assert headerless_len(filter_result.units) == 0

    def test_simplefail(self):
        """Checks that an obviously wrong string fails."""
        self.unit.target = "REST"
        filter_result = self.filter(self.translationstore)
        print(filter_result)
        print(filter_result.units)
        assert "startcaps" in first_translatable(filter_result).geterrors()

    def test_variables_across_lines(self):
        """Test that variables can span lines and still fail/pass."""
        self.unit.source = '"At &timeBombURL."\n"label;."'
        self.unit.target = '"Tydens &tydBombURL."\n"etiket;."'
        filter_result = self.filter(self.translationstore)
        assert headerless_len(filter_result.units) == 0

    def test_ignore_if_already_marked(self):
        """
        Check that we don't add another failing marker if the message is
        already marked as failed.
        """
        self.unit.target = ""
        filter_result = self.filter(
            self.translationstore, cmdlineoptions=["--test=untranslated"]
        )
        errors = first_translatable(filter_result).geterrors()
        assert len(errors) == 1
        assert "untranslated" in errors

        # Run a filter test on the result, to check that it doesn't mark the
        # same error twice.
        filter_result2 = self.filter(
            filter_result, cmdlineoptions=["--test=untranslated"]
        )
        errors = first_translatable(filter_result2).geterrors()
        assert len(errors) == 1
        assert "untranslated" in errors

    def test_non_existant_check(self):
        """Check that we report an error if a user tries to run a non-existant test."""
        filter_result = self.filter(
            self.translationstore, cmdlineoptions=["-t nonexistant"]
        )
        # TODO Not sure how to check for the stderror result of: warning: could
        # not find filter  nonexistant
        assert headerless_len(filter_result.units) == 0

    def test_list_all_tests(self):
        """Lists all available tests."""
        filter_result = self.filter(self.translationstore, cmdlineoptions=["-l"])
        # TODO again not sure how to check the stderror output
        assert headerless_len(filter_result.units) == 0

    def test_test_against_fuzzy(self):
        """Test whether to run tests against fuzzy translations."""
        self.unit.markfuzzy()

        filter_result = self.filter(self.translationstore, cmdlineoptions=["--fuzzy"])
        assert "isfuzzy" in first_translatable(filter_result).geterrors()

        filter_result = self.filter(self.translationstore, cmdlineoptions=["--nofuzzy"])
        assert headerless_len(filter_result.units) == 0

        # Re-initialize the translation store object in order to get an unfuzzy
        # unit with no filter notes.
        self.setup_method(self)

        filter_result = self.filter(self.translationstore, cmdlineoptions=["--fuzzy"])
        assert headerless_len(filter_result.units) == 0

        filter_result = self.filter(self.translationstore, cmdlineoptions=["--nofuzzy"])
        assert headerless_len(filter_result.units) == 0

    def test_test_against_review(self):
        """Test whether to run tests against translations marked for review."""
        self.unit.markreviewneeded()
        filter_result = self.filter(self.translationstore, cmdlineoptions=["--review"])
        assert first_translatable(filter_result).isreview()

        filter_result = self.filter(
            self.translationstore, cmdlineoptions=["--noreview"]
        )
        assert headerless_len(filter_result.units) == 0

        # Re-initialize the translation store object.
        self.setup_method(self)

        filter_result = self.filter(self.translationstore, cmdlineoptions=["--review"])
        assert headerless_len(filter_result.units) == 0
        filter_result = self.filter(
            self.translationstore, cmdlineoptions=["--noreview"]
        )
        assert headerless_len(filter_result.units) == 0

    def test_isfuzzy(self):
        """Tests the extraction of items marked fuzzy."""
        self.unit.markfuzzy()

        filter_result = self.filter(
            self.translationstore, cmdlineoptions=["--test=isfuzzy"]
        )
        assert "isfuzzy" in first_translatable(filter_result).geterrors()

        self.unit.markfuzzy(False)
        filter_result = self.filter(
            self.translationstore, cmdlineoptions=["--test=isfuzzy"]
        )
        assert headerless_len(filter_result.units) == 0

    def test_isreview(self):
        """Tests the extraction of items marked review."""
        filter_result = self.filter(
            self.translationstore, cmdlineoptions=["--test=isreview"]
        )
        assert headerless_len(filter_result.units) == 0

        self.unit.markreviewneeded()
        filter_result = self.filter(
            self.translationstore, cmdlineoptions=["--test=isreview"]
        )
        assert first_translatable(filter_result).isreview()

    def test_notes(self):
        """Tests the optional adding of notes."""
        # let's make sure we trigger the 'long' and/or 'doubleword' test
        self.unit.target = "asdf asdf asdf asdf asdf asdf asdf"
        filter_result = self.filter(self.translationstore)
        assert headerless_len(filter_result.units) == 1
        assert first_translatable(filter_result).geterrors()

        # now we remove the existing error. self.unit is changed since we copy
        # units - very naughty
        if isinstance(self.unit, xliff.xliffunit):
            self.unit.removenotes(origin="pofilter")
        else:
            self.unit.removenotes()
        filter_result = self.filter(self.translationstore, cmdlineoptions=["--nonotes"])
        assert headerless_len(filter_result.units) == 1
        assert len(first_translatable(filter_result).geterrors()) == 0

    def test_unicode(self):
        """
        Tests that we can handle UTF-8 encoded characters when there is no
        known header specified encoding.
        """
        self.unit.source = "Bézier curve"
        self.unit.target = "Bézier-kurwe"
        filter_result = self.filter(self.translationstore)
        assert headerless_len(filter_result.units) == 0

    def test_preconditions(self):
        """Tests that the preconditions work correctly."""
        self.unit.source = "File"
        self.unit.target = ""
        filter_result = self.filter(self.translationstore)
        # We should only get one error (untranslated), and nothing else
        assert headerless_len(filter_result.units) == 1
        unit = first_translatable(filter_result)
        assert len(unit.geterrors()) == 1


class TestPOFilter(BaseTestFilter):
    """Test class for po-specific tests."""

    filetext = '#: test.c\nmsgid "test"\nmsgstr "rest"\n'
    filename = "test.po"

    def setup_method(self, method):
        self.translationstore = self.parse_text(self.filetext)
        self.unit = first_translatable(self.translationstore)

    def test_msgid_comments(self):
        """Tests that msgid comments don't feature anywhere."""
        posource = """
msgid "_: Capital.  ACRONYMN. (msgid) comment 3. %d Extra sentence.\\n"
"cow"
msgstr "koei"
"""
        pofile = self.parse_text(posource)
        filter_result = self.filter(pofile)
        if headerless_len(filter_result.units):
            print(first_translatable(filter_result))
        assert headerless_len(filter_result.units) == 0


class TestXliffFilter(BaseTestFilter):
    """Test class for xliff-specific tests."""

    filetext = """<?xml version="1.0" encoding="utf-8"?>
<xliff version="1.1" xmlns="urn:oasis:names:tc:xliff:document:1.1">
<file original='NoName' source-language="en" datatype="plaintext">
  <body>
    <trans-unit approved="yes">
      <source>test</source>
      <target>rest</target>
    </trans-unit>
  </body>
</file>
</xliff>"""
    filename = "test.xlf"

    def set_store_review(self, review=True):
        self.filetext = """<?xml version="1.0" encoding="utf-8"?>
<xliff version="1.1" xmlns="urn:oasis:names:tc:xliff:document:1.1">
<file datatype="po" original="example.po" source-language="en-US">
  <body>
    <trans-unit approved="yes">
      <source>test</source>
      <target>rest</target>
    </trans-unit>
  </body>
</file>
</xliff>"""

        self.translationstore = self.parse_text(self.filetext)
        self.unit = first_translatable(self.translationstore)

    def setup_method(self, method):
        self.translationstore = self.parse_text(self.filetext)
        self.unit = first_translatable(self.translationstore)


class TestTMXFilter(BaseTestFilter):
    """Test class for TMX-specific tests."""

    filetext = """<!DOCTYPE tmx SYSTEM "tmx14.dtd">
<tmx version="1.4">
  <header creationtool="Translate Toolkit"
          creationtoolversion="1.1.1rc1" segtype="sentence" o-tmf="UTF-8"
          adminlang="en" srclang="en" datatype="PlainText"/>
  <body>
    <tu>
      <tuv xml:lang="en">
        <seg>test</seg>
      </tuv>
      <tuv xml:lang="af">
        <seg>rest</seg>
      </tuv>
    </tu>
  </body>
</tmx>"""
    filename = "test.tmx"

    def setup_method(self, method):
        self.translationstore = self.parse_text(self.filetext)
        self.unit = first_translatable(self.translationstore)

    def test_test_against_fuzzy(self):
        """TMX doesn't support fuzzy."""

    def test_test_against_review(self):
        """TMX doesn't support review."""

    def test_isfuzzy(self):
        """TMX doesn't support fuzzy."""

    def test_isreview(self):
        """TMX doesn't support review."""


class TestRomanianPOFilter(TestPOFilter):
    """Test class for po-specific Romanian tests."""

    def test_romanian_cedillas(self):
        """Test the Romanian cedillas check."""
        posource = """
msgid "cow"
msgstr "blaŞbla"
"""
        pofile = self.parse_text(posource)
        filter_result = self.filter(
            pofile, cmdlineoptions=["--language=ro", "--test=cedillas"]
        )
        errors = first_translatable(filter_result).geterrors()
        assert len(errors) == 1
        assert "cedillas" in errors

        posource = """
msgid "cow"
msgstr "blaSbla"
"""
        pofile = self.parse_text(posource)
        filter_result = self.filter(
            pofile, cmdlineoptions=["--language=ro", "--test=cedillas"]
        )
        errors = first_translatable(filter_result).geterrors()
        assert len(errors) == 0
        assert "cedillas" not in errors

    def test_romanian_niciun(self):
        """Test the Romanian niciun check."""
        posource = """
msgid "cow"
msgstr "bla nici un bla"
"""
        pofile = self.parse_text(posource)
        filter_result = self.filter(
            pofile, cmdlineoptions=["--language=ro", "--test=niciun_nicio"]
        )
        errors = first_translatable(filter_result).geterrors()
        assert len(errors) == 1
        assert "niciun_nicio" in errors

        posource = """
msgid "cow"
msgstr "bla niciun bla"
"""
        pofile = self.parse_text(posource)
        filter_result = self.filter(
            pofile, cmdlineoptions=["--language=ro", "--test=niciun_nicio"]
        )
        errors = first_translatable(filter_result).geterrors()
        assert len(errors) == 0
        assert "niciun_nicio" not in errors

    def test_romanian_nicio(self):
        """Test the Romanian nicio check."""
        posource = """
msgid "cow"
msgstr "bla nici o bla"
"""
        pofile = self.parse_text(posource)
        filter_result = self.filter(
            pofile, cmdlineoptions=["--language=ro", "--test=niciun_nicio"]
        )
        errors = first_translatable(filter_result).geterrors()
        assert len(errors) == 1
        assert "niciun_nicio" in errors

        posource = """
msgid "cow"
msgstr "bla nicio bla"
"""
        pofile = self.parse_text(posource)
        filter_result = self.filter(
            pofile, cmdlineoptions=["--language=ro", "--test=niciun_nicio"]
        )
        errors = first_translatable(filter_result).geterrors()
        assert len(errors) == 0
        assert "niciun_nicio" not in errors
