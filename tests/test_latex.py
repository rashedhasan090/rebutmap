import os
import tempfile
import unittest

from rebutmap.latex import Paper

DOC = r"""\documentclass{article}
\begin{document}
\section{Intro}\label{sec:intro}
\section*{Acknowledgments}
\section{Method}
\subsection{Setup}
\subsubsection{Details}
\begin{figure}\begin{subfigure}\caption{left}\end{subfigure}\caption{Both}\label{fig:both}\end{figure}
\begin{figure*}\caption{Wide}\label{fig:wide}\end{figure*}
\begin{figure}\includegraphics{nocap}\end{figure}
\begin{equation}x=1\label{eq:x}\end{equation}
\begin{equation*}y=2\end{equation*}
\begin{align}a&=b\\ c&=d\nonumber\\ e&=f\label{eq:e}\end{align}
\begin{table}\caption{T}\label{tab:t}\end{table}
% \section{Commented out}
\appendix
\section{Proofs}\subsection{Lemma 1}
\end{document}
"""


class PaperTests(unittest.TestCase):
    def setUp(self):
        self.p = Paper(DOC)

    def test_section_numbers(self):
        self.assertEqual(self.p.section_numbers, {"1", "2", "2.1", "2.1.1", "A", "A.1"})

    def test_counters(self):
        self.assertEqual(self.p.figures, 2)
        self.assertEqual(self.p.tables, 1)
        self.assertEqual(self.p.equations, 3)

    def test_labels(self):
        self.assertEqual(self.p.labels["fig:both"], ("figure", "1"))
        self.assertEqual(self.p.labels["fig:wide"], ("figure", "2"))
        self.assertEqual(self.p.labels["eq:x"], ("equation", "1"))
        self.assertEqual(self.p.labels["eq:e"], ("equation", "3"))
        self.assertEqual(self.p.labels["sec:intro"], ("section", "1"))

    def test_check_locator(self):
        self.assertIsNone(self.p.check_locator("section", "2.1"))
        self.assertIsNotNone(self.p.check_locator("section", "4"))
        self.assertIsNone(self.p.check_locator("appendix", "A"))
        self.assertIsNotNone(self.p.check_locator("appendix", "B"))
        self.assertIsNone(self.p.check_locator("figure", "2"))
        self.assertIsNotNone(self.p.check_locator("figure", "3"))
        self.assertIsNone(self.p.check_locator("table", "A1"))
        self.assertIsNone(self.p.check_locator("ref", "fig:both, tab:t"))
        self.assertIn("eq:nope", self.p.check_locator("ref", "eq:nope"))
        self.assertIsNone(self.p.check_locator("line", "999"))

    def test_unit_text_spans_subsections(self):
        method = self.p.unit_by_number("2")
        setup = self.p.unit_by_number("2.1")
        self.assertGreater(len(method.words), len(setup.words))
        self.assertIs(self.p.unit_by_title("method"), method)

    def test_input_is_followed(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "sec"))
            with open(os.path.join(d, "main.tex"), "w") as f:
                f.write("\\begin{document}\\section{A}\\input{sec/b}\\end{document}")
            with open(os.path.join(d, "sec", "b.tex"), "w") as f:
                f.write("\\section{B} hello world")
            p = Paper.from_file(os.path.join(d, "main.tex"))
            self.assertEqual(p.section_numbers, {"1", "2"})
            self.assertGreater(p.corpus.coverage(["hello", "world"]), 0.9)


if __name__ == "__main__":
    unittest.main()
