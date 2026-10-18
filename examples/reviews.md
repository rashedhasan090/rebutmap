# Reviewer 1

1. The novelty relative to prior agent-tracing tools is unclear. Please position the work
   against existing tracing systems.
2. The evaluation uses only two datasets, which limits how far the results generalize.
3. The threats to validity section does not discuss selection bias in the benchmark.

# Reviewer 2

W1: There is no ablation of the retrieval component, so its contribution is unknown.
W2: The threshold of 0.7 seems arbitrary and is not justified anywhere.
Q1: How does the approach scale to traces with more than 10,000 events?

# Meta-review

The authors should address the evaluation concerns raised by both reviewers, in particular
the limited datasets and the missing scaling evidence.
