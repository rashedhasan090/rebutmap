import unittest

from rebutmap.checks import analyze
from rebutmap.latex import Paper

OLD = r"""\begin{document}
\section{Intro} Agents call tools.
\section{Eval} We use two datasets.
\begin{table}\caption{A}\end{table}
\section{Threats} Tasks come from public repositories only.
\end{document}"""
NEW = r"""\begin{document}
\section{Intro} Agents call tools. Unlike prior tracers, we reconstruct causal links offline.
\section{Eval} We use three datasets.
\begin{table}\caption{A}\end{table}\begin{table}\caption{B}\end{table}
\section{Threats} Tasks come from public repositories only.
\end{document}"""
REVIEWS = """# Reviewer 1
1. The novelty over prior tracing tools is unclear.
2. Only two datasets are used in the evaluation.
3. Selection bias is not discussed at all.
# Reviewer 2
1. The threshold choice is never justified in the paper.
"""


def codes(result, target=None):
    return sorted(f.code for f in result["findings"] if target is None or f.target == target)


class CheckTests(unittest.TestCase):
    def run_case(self, response, reviews=REVIEWS, paper=True, before=True):
        return analyze(reviews, response, paper=Paper(NEW) if paper else None,
                       before=Paper(OLD) if before else None)

    def test_clean_letter_has_no_errors(self):
        resp = """# Response to Reviewer 1
> 1. The novelty over prior tracing tools is unclear.
Response: We added "Unlike prior tracers, we reconstruct causal links offline." to Section 1.
> 2. Only two datasets are used in the evaluation.
Response: We added a third dataset in Section 2 and Table 2.
> 3. Selection bias is not discussed at all.
Response: We respectfully disagree; the benchmark is stratified by repository size and language.
# Response to Reviewer 2
> 1. The threshold choice is never justified in the paper.
Response: The threshold is the elbow of the precision-recall curve, which we explain in our reply.
"""
        r = self.run_case(resp)
        self.assertEqual(codes(r), [])
        self.assertEqual(set(r["status"].values()), {"answered"})

    def test_unaddressed(self):
        r = self.run_case("# Response to Reviewer 1\n> 1. The novelty over prior tracing tools is unclear.\n"
                          "Response: We added a paragraph to Section 1.\n")
        self.assertEqual(r["status"]["R1.2"], "missing")
        self.assertIn("unaddressed", codes(r, "R2.1"))

    def test_dangling_locators(self):
        r = self.run_case("R1.1: We added Table 3, Section 7 and \\ref{fig:none}.\n")
        msgs = [f.message for f in r["findings"] if f.code == "dangling-locator"]
        self.assertEqual(len(msgs), 3)

    def test_phantom_quote_and_old_text(self):
        r = self.run_case('R1.1: We added Section 1, which now says "we prove soundness for all agent graphs".\n'
                          'R1.2: We replaced "We use two datasets." with "We use three datasets." in Section 2.\n')
        self.assertEqual(codes(r, "R1.1"), ["phantom-quote"])
        self.assertNotIn("phantom-quote", codes(r, "R1.2"))

    def test_quote_only_in_previous_version(self):
        r = self.run_case('R1.2: Section 2 now reads "We use two datasets in total here".\n')
        f = [f for f in r["findings"] if f.code == "phantom-quote"]
        self.assertTrue(f)

    def test_already_present_and_untouched(self):
        r = self.run_case('R1.3: We revised Section 3, adding "Tasks come from public repositories only."\n')
        self.assertEqual(codes(r, "R1.3"), ["already-present", "untouched-section"])

    def test_untouched_needs_before(self):
        r = self.run_case("R1.3: We revised Section 3.\n", before=False)
        self.assertEqual(codes(r, "R1.3"), [])

    def test_mislabeled(self):
        r = self.run_case("**R1.3** Only two datasets are used in the evaluation.\nResponse: Added Table 2.\n")
        self.assertIn("mislabeled", codes(r))
        self.assertEqual(r["status"]["R1.2"], "answered")
        self.assertEqual(r["status"]["R1.3"], "missing")

    def test_hollow_and_unlocated(self):
        r = self.run_case("R1.1: Thank you for this insightful comment. We agree.\n"
                          "R1.2: We have clarified this throughout the paper.\n")
        self.assertEqual(codes(r, "R1.1"), ["hollow"])
        self.assertEqual(codes(r, "R1.2"), ["unlocated-change"])

    def test_deferred(self):
        r = self.run_case("R1.3: Selection bias is beyond the scope of this paper, but we discuss it as future work in Section 3.\n")
        self.assertIn("deferred", codes(r, "R1.3"))

    def test_crossref(self):
        r = self.run_case("R1.1: We added Section 1.\nR2.1: See our response to R1.1.\nR1.2: See R1.3.\nR1.3: See R9.9.\n")
        self.assertEqual(codes(r, "R2.1"), [])
        self.assertEqual(r["status"]["R2.1"], "answered")
        broken = [f.message for f in r["findings"] if f.code == "broken-crossref"]
        self.assertEqual(len(broken), 1)
        self.assertIn("R9.9", broken[0])

    def test_crossref_to_unanswered_comment(self):
        r = analyze("# Reviewer 1\n1. aaa bbb ccc ddd\n2. eee fff ggg hhh\n", "R1.1: See R1.2.\n")
        self.assertIn("broken-crossref", codes(r))
        self.assertEqual(r["status"]["R1.2"], "crossref")

    def test_orphan_and_empty(self):
        r = self.run_case("R3.4: We fixed it in Section 1.\nR1.1 The novelty over prior tracing tools is unclear.\nResponse:\n")
        self.assertIn("orphan-response", codes(r))
        self.assertEqual(codes(r, "R1.1"), ["empty-response"])

    def test_reviewer_quote_is_not_phantom(self):
        r = self.run_case('R2.1: The reviewer notes that "The threshold choice is never justified in the paper." '
                          'We added a justification in Section 2.\n')
        self.assertNotIn("phantom-quote", codes(r))

    def test_no_paper_skips_paper_checks(self):
        r = self.run_case('R1.1: We added Table 9 with "text that is nowhere at all in the paper".\n',
                          paper=False, before=False)
        self.assertNotIn("dangling-locator", codes(r))
        self.assertNotIn("phantom-quote", codes(r))


if __name__ == "__main__":
    unittest.main()
