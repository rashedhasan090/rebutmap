import unittest

from rebutmap.structure import heading_reviewer, parse, tex_letter_to_text


class HeadingTests(unittest.TestCase):
    def test_common_headings(self):
        self.assertEqual(heading_reviewer("# Reviewer 1"), "R1")
        self.assertEqual(heading_reviewer("**Reviewer #2 (Remarks to the Author):**"), "R2")
        self.assertEqual(heading_reviewer("## Response to Reviewer 3"), "R3")
        self.assertEqual(heading_reviewer("Referee 4"), "R4")
        self.assertEqual(heading_reviewer("R5:"), "R5")
        self.assertEqual(heading_reviewer("# Meta-review"), "AE")
        self.assertEqual(heading_reviewer("Response to the Associate Editor"), "AE")

    def test_prose_is_not_a_heading(self):
        self.assertIsNone(heading_reviewer("Reviewer 2 also raised a concern about the baselines in the paper."))
        self.assertIsNone(heading_reviewer("R1.2 The baselines are weak."))
        self.assertIsNone(heading_reviewer("> Reviewer 1"))


class ParseTests(unittest.TestCase):
    def test_numbered_and_labelled_items(self):
        items = parse("# Reviewer 1\n1. First point here.\n   continued.\n2. Second.\n"
                      "# Reviewer 2\nW1: weak ablation\nQ1: why 0.7?\n")
        self.assertEqual([i.id for i in items], ["R1.1", "R1.2", "R2.W1", "R2.Q1"])
        self.assertEqual(items[0].text, "First point here. continued.")
        self.assertEqual(items[0].line, 2)

    def test_dotted_comment_label_sets_reviewer(self):
        items = parse("Comment 2.3: the proof skips a case.\n", default_reviewer="R1")
        self.assertEqual(items[0].id, "R2.3")
        self.assertTrue(items[0].tagged)

    def test_bullets_and_paragraph_fallback(self):
        items = parse("# Reviewer 1\n- alpha issue\n- beta issue\n# Reviewer 2\n"
                      "The paper is unclear about the threat model.\n\nThe related work misses key systems.\n")
        self.assertEqual([i.id for i in items], ["R1.1", "R1.2", "R2.1", "R2.2"])

    def test_paragraph_fallback_skips_tiny_labels(self):
        items = parse("# Reviewer 1\nWeaknesses:\n\nThe evaluation is too small to be convincing.\n")
        self.assertEqual(len(items), 1)

    def test_explicit_tag_variants(self):
        text = "R1.1 a\nR1-C2 b\nR2Q3 c\n[R3.W1] d\nReviewer 4, Comment 5: e\n"
        items = parse(text, "response")
        self.assertEqual([i.id for i in items], ["R1.1", "R1.2", "R2.Q3", "R3.W1", "R4.5"])
        self.assertTrue(all(i.tagged for i in items))

    def test_numbered_list_inside_response_does_not_split(self):
        text = ("# Response to Reviewer 1\n> 1. The novelty is unclear.\nResponse: We changed:\n"
                "1. the intro\n2. the related work\n> 2. Only two datasets.\nWe added one.\n")
        items = parse(text, "response")
        self.assertEqual([i.id for i in items], ["R1.1", "R1.2"])
        self.assertIn("2. the related work", items[0].lines)

    def test_duplicate_ids_get_suffix(self):
        items = parse("# Reviewer 1\n1. a b c d\n# Reviewer 1\n1. e f g h\n")
        self.assertEqual([i.id for i in items], ["R1.1", "R1.1#2"])

    def test_tex_letter(self):
        tex = (r"\documentclass{article}\begin{document}\section*{Reviewer 1}"
               "\n\\begin{quote}The novelty is unclear.\\end{quote}\n"
               r"\textbf{Response:} We added Section~2." "\n\\end{document}")
        items = parse(tex_letter_to_text(tex), "response")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].reviewer, "R1")
        self.assertTrue(items[0].lines[0].startswith(">"))


if __name__ == "__main__":
    unittest.main()
