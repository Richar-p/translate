from io import BytesIO

from pytest import mark

from translate.storage import po, xliff
from translate.tools import pretranslate

from ..convert import test_convert


class TestPretranslate:
    xliff_skeleton = """<?xml version="1.0" encoding="utf-8"?>
<xliff version="1.1" xmlns="urn:oasis:names:tc:xliff:document:1.1">
        <file original="doc.txt" source-language="en-US">
                <body>
                        %s
                </body>
        </file>
</xliff>"""

    @staticmethod
    def pretranslatepo(input_source, template_source=None):
        """Helper that converts strings to po source without requiring files."""
        input_file = BytesIO(input_source.encode())
        template_file = BytesIO(template_source.encode()) if template_source else None
        output_file = BytesIO()

        pretranslate.pretranslate_file(input_file, output_file, template_file)
        output_file.seek(0)
        return po.pofile(output_file.read())

    @staticmethod
    def pretranslatexliff(input_source, template_source=None):
        """Helper that converts strings to po source without requiring files."""
        input_file = BytesIO(input_source)
        template_file = BytesIO(template_source) if template_source else None
        output_file = BytesIO()

        pretranslate.pretranslate_file(input_file, output_file, template_file)
        output_file.seek(0)
        return xliff.xlifffile(output_file.read())

    @staticmethod
    def singleunit(pofile):
        """
        Checks that the pofile contains a single non-header unit, and
        returns it.
        """
        if len(pofile.units) == 2 and pofile.units[0].isheader():
            print(pofile.units[1])
            return pofile.units[1]
        print(pofile.units[0])
        return pofile.units[0]

    def test_pretranslatepo_blank(self):
        """
        Checks that the pretranslatepo function is working for a simple file
        initialisation.
        """
        input_source = f"""#: simple.label{po.lsep}simple.accesskey\nmsgid "A &hard coded newline.\\n"\nmsgstr ""\n"""
        newpo = self.pretranslatepo(input_source)
        assert str(self.singleunit(newpo)) == input_source

    def test_merging_simple(self):
        """Checks that the pretranslatepo function is working for a simple merge."""
        input_source = f"""#: simple.label{po.lsep}simple.accesskey\nmsgid "A &hard coded newline.\\n"\nmsgstr ""\n"""
        template_source = f"""#: simple.label{po.lsep}simple.accesskey\nmsgid "A &hard coded newline.\\n"\nmsgstr "&Hart gekoeerde nuwe lyne\\n"\n"""
        newpo = self.pretranslatepo(input_source, template_source)
        assert str(self.singleunit(newpo)) == template_source

    def test_merging_messages_marked_fuzzy(self):
        """Test that when we merge PO files with a fuzzy message that it remains fuzzy."""
        input_source = f"""#: simple.label{po.lsep}simple.accesskey\nmsgid "A &hard coded newline.\\n"\nmsgstr ""\n"""
        template_source = f"""#: simple.label{po.lsep}simple.accesskey\n#, fuzzy\nmsgid "A &hard coded newline.\\n"\nmsgstr "&Hart gekoeerde nuwe lyne\\n"\n"""
        newpo = self.pretranslatepo(input_source, template_source)
        assert str(self.singleunit(newpo)) == template_source

    def test_merging_plurals_with_fuzzy_matching(self):
        """Test that when we merge PO files with a fuzzy message that it remains fuzzy."""
        input_source = r"""#: file.cpp:2
msgid "%d manual"
msgid_plural "%d manuals"
msgstr[0] ""
msgstr[1] ""
"""
        template_source = r"""#: file.cpp:3
#, fuzzy
msgid "%d manual"
msgid_plural "%d manuals"
msgstr[0] "%d handleiding."
msgstr[1] "%d handleidings."
"""
        # The #: comment and msgid's are different between the pot and the po
        poexpected = r"""#: file.cpp:2
#, fuzzy
msgid "%d manual"
msgid_plural "%d manuals"
msgstr[0] "%d handleiding."
msgstr[1] "%d handleidings."
"""
        newpo = self.pretranslatepo(input_source, template_source)
        assert str(self.singleunit(newpo)) == poexpected

    @mark.xfail(reason="Not Implemented")
    def test_merging_msgid_change(self):
        """
        Tests that if the msgid changes but the location stays the same that
        we merge.
        """
        input_source = """#: simple.label\n#: simple.accesskey\nmsgid "Its &hard coding a newline.\\n"\nmsgstr ""\n"""
        template_source = """#: simple.label\n#: simple.accesskey\nmsgid "A &hard coded newline.\\n"\nmsgstr "&Hart gekoeerde nuwe lyne\\n"\n"""
        poexpected = """#: simple.label\n#: simple.accesskey\n#, fuzzy\nmsgid "Its &hard coding a newline.\\n"\nmsgstr "&Hart gekoeerde nuwe lyne\\n"\n"""
        newpo = self.pretranslatepo(input_source, template_source)
        print(bytes(newpo))
        assert bytes(newpo).decode("utf-8") == poexpected

    def test_merging_location_change(self):
        """
        Tests that if the location changes but the msgid stays the same that
        we merge.
        """
        input_source = f"""#: new_simple.label{po.lsep}new_simple.accesskey\nmsgid "A &hard coded newline.\\n"\nmsgstr ""\n"""
        template_source = f"""#: simple.label{po.lsep}simple.accesskey\nmsgid "A &hard coded newline.\\n"\nmsgstr "&Hart gekoeerde nuwe lyne\\n"\n"""
        poexpected = f"""#: new_simple.label{po.lsep}new_simple.accesskey\nmsgid "A &hard coded newline.\\n"\nmsgstr "&Hart gekoeerde nuwe lyne\\n"\n"""
        newpo = self.pretranslatepo(input_source, template_source)
        print(bytes(newpo))
        assert bytes(newpo).decode("utf-8") == poexpected

    def test_merging_location_and_whitespace_change(self):
        """
        Test that even if the location changes that if the msgid only has
        whitespace changes we can still merge.
        """
        input_source = f"""#: singlespace.label{po.lsep}singlespace.accesskey\nmsgid "&We have spaces"\nmsgstr ""\n"""
        template_source = f"""#: doublespace.label{po.lsep}doublespace.accesskey\nmsgid "&We  have  spaces"\nmsgstr "&One  het  spasies"\n"""
        poexpected = f"""#: singlespace.label{po.lsep}singlespace.accesskey\n#, fuzzy\nmsgid "&We have spaces"\nmsgstr "&One  het  spasies"\n"""
        newpo = self.pretranslatepo(input_source, template_source)
        print(bytes(newpo))
        assert bytes(newpo).decode("utf-8") == poexpected

    @mark.xfail(reason="Not Implemented")
    def test_merging_accelerator_changes(self):
        """
        Test that a change in the accelerator localtion still allows
        merging.
        """
        input_source = """#: someline.c\nmsgid "A&bout"\nmsgstr ""\n"""
        template_source = """#: someline.c\nmsgid "&About"\nmsgstr "&Info"\n"""
        poexpected = """#: someline.c\nmsgid "A&bout"\nmsgstr "&Info"\n"""
        newpo = self.pretranslatepo(input_source, template_source)
        print(bytes(newpo))
        assert bytes(newpo).decode("utf-8") == poexpected

    @mark.xfail(reason="Not Implemented")
    def test_lines_cut_differently(self):
        """
        Checks that the correct formatting is preserved when pot an po lines
        differ.
        """
        input_source = (
            """#: simple.label\nmsgid "Line split "\n"differently"\nmsgstr ""\n"""
        )
        template_source = """#: simple.label\nmsgid "Line"\n" split differently"\nmsgstr "Lyne verskillend gesny"\n"""
        newpo = self.pretranslatepo(input_source, template_source)
        newpounit = self.singleunit(newpo)
        assert str(newpounit) == template_source

    def test_merging_automatic_comments_dont_duplicate(self):
        """Ensure that we can merge #. comments correctly."""
        input_source = """#. Row 35\nmsgid "&About"\nmsgstr ""\n"""
        template_source = """#. Row 35\nmsgid "&About"\nmsgstr "&Info"\n"""
        newpo = self.pretranslatepo(input_source, template_source)
        newpounit = self.singleunit(newpo)
        assert str(newpounit) == template_source

    def test_merging_automatic_comments_new_overides_old(self):
        """Ensure that new #. comments override the old comments."""
        input_source = """#. new comment\n#: someline.c\nmsgid "&About"\nmsgstr ""\n"""
        template_source = (
            """#. old comment\n#: someline.c\nmsgid "&About"\nmsgstr "&Info"\n"""
        )
        poexpected = (
            """#. new comment\n#: someline.c\nmsgid "&About"\nmsgstr "&Info"\n"""
        )
        newpo = self.pretranslatepo(input_source, template_source)
        newpounit = self.singleunit(newpo)
        assert str(newpounit) == poexpected

    def test_merging_comments_with_blank_comment_lines(self):
        """
        Test that when we merge a comment that has a blank line we keep the
        blank line.
        """
        input_source = """#: someline.c\nmsgid "About"\nmsgstr ""\n"""
        template_source = """# comment1\n#\n# comment2\n#: someline.c\nmsgid "About"\nmsgstr "Omtrent"\n"""
        poexpected = template_source
        newpo = self.pretranslatepo(input_source, template_source)
        newpounit = self.singleunit(newpo)
        assert str(newpounit) == poexpected

    def test_empty_commentlines(self):
        input_source = """#: paneSecurity.title
msgid "Security"
msgstr ""
"""
        template_source = """# - Contributor(s):
# -
# - Alternatively, the
# -
#: paneSecurity.title
msgid "Security"
msgstr "Sekuriteit"
"""
        poexpected = template_source
        newpo = self.pretranslatepo(input_source, template_source)
        newpounit = self.singleunit(newpo)
        print("expected")
        print(poexpected)
        print("got:")
        print(str(newpounit))
        assert str(newpounit) == poexpected

    def test_merging_msgidcomments(self):
        """Ensure that we can merge msgidcomments messages."""
        input_source = r"""#: window.width
msgid ""
"_: Do not translate this.\n"
"36em"
msgstr ""
"""
        template_source = r"""#: window.width
msgid ""
"_: Do not translate this.\n"
"36em"
msgstr "36em"
"""
        newpo = self.pretranslatepo(input_source, template_source)
        newpounit = self.singleunit(newpo)
        assert str(newpounit) == template_source

    def test_merging_plurals(self):
        """Ensure that we can merge plural messages."""
        input_source = (
            """msgid "One"\nmsgid_plural "Two"\nmsgstr[0] ""\nmsgstr[1] ""\n"""
        )
        template_source = """msgid "One"\nmsgid_plural "Two"\nmsgstr[0] "Een"\nmsgstr[1] "Twee"\nmsgstr[2] "Drie"\n"""
        newpo = self.pretranslatepo(input_source, template_source)
        print(newpo)
        newpounit = self.singleunit(newpo)
        assert str(newpounit) == template_source

    def test_merging_resurect_obsolete_messages(self):
        """
        Check that we can reuse old obsolete messages if the message comes
        back.
        """
        input_source = """#: resurect.c\nmsgid "&About"\nmsgstr ""\n"""
        template_source = """#~ msgid "&About"\n#~ msgstr "&Omtrent"\n"""
        expected = """#: resurect.c\nmsgid "&About"\nmsgstr "&Omtrent"\n"""
        newpo = self.pretranslatepo(input_source, template_source)
        print(bytes(newpo))
        assert bytes(newpo).decode("utf-8") == expected

    def test_merging_comments(self):
        """Test that we can merge comments correctly."""
        input_source = """#. Don't do it!\n#: file.py:1\nmsgid "One"\nmsgstr ""\n"""
        template_source = (
            """#. Don't do it!\n#: file.py:2\nmsgid "One"\nmsgstr "Een"\n"""
        )
        poexpected = """#. Don't do it!\n#: file.py:1\nmsgid "One"\nmsgstr "Een"\n"""
        newpo = self.pretranslatepo(input_source, template_source)
        print(newpo)
        newpounit = self.singleunit(newpo)
        assert str(newpounit) == poexpected

    def test_merging_typecomments(self):
        """Test that we can merge with typecomments."""
        input_source = """#: file.c:1\n#, c-format\nmsgid "%d pipes"\nmsgstr ""\n"""
        template_source = """#: file.c:2\nmsgid "%d pipes"\nmsgstr "%d pype"\n"""
        poexpected = (
            """#: file.c:1\n#, c-format\nmsgid "%d pipes"\nmsgstr "%d pype"\n"""
        )
        newpo = self.pretranslatepo(input_source, template_source)
        newpounit = self.singleunit(newpo)
        print(newpounit)
        assert str(newpounit) == poexpected

        input_source = """#: file.c:1\n#, c-format\nmsgid "%d computers"\nmsgstr ""\n"""
        template_source = """#: file.c:2\n#, c-format\nmsgid "%s computers "\nmsgstr "%s-rekenaars"\n"""
        poexpected = """#: file.c:1\n#, fuzzy, c-format\nmsgid "%d computers"\nmsgstr "%s-rekenaars"\n"""
        newpo = self.pretranslatepo(input_source, template_source)
        newpounit = self.singleunit(newpo)
        assert newpounit.isfuzzy()
        assert newpounit.hastypecomment("c-format")

    def test_xliff_states(self):
        """Test correct maintenance of XLIFF states."""
        xlf_template = self.xliff_skeleton % (
            """<trans-unit id="1" xml:space="preserve">
                   <source> File  1 </source>
               </trans-unit>"""
        )
        xlf_old = self.xliff_skeleton % (
            """<trans-unit id="1" xml:space="preserve" approved="yes">
                   <source> File  1 </source>
                   <target> Lêer 1 </target>
               </trans-unit>"""
        )

        template = xliff.xlifffile.parsestring(xlf_template)
        old = xliff.xlifffile.parsestring(xlf_old)
        # Serialize files
        new = self.pretranslatexliff(bytes(template), bytes(old))
        print(bytes(old))
        print("---")
        print(bytes(new))
        assert new.units[0].isapproved()
        # Layout might have changed, so we won't compare the serialised
        # versions


class TestPretranslateCommand(test_convert.TestConvertCommand, TestPretranslate):
    """Tests running actual pretranslate commands on files."""

    convertmodule = pretranslate
    expected_options = [
        "-t TEMPLATE, --template=TEMPLATE",
        "--tm",
        "-s MIN_SIMILARITY, --similarity=MIN_SIMILARITY",
        "--nofuzzymatching",
    ]
