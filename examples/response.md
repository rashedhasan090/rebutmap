# Response to Reviewer 1

> 1. The novelty relative to prior agent-tracing tools is unclear.

Response: We added a comparison with existing tracing systems in Section 2. The new text reads
"Unlike prior tracing systems, our approach reconstructs causal links between tool calls offline."

> 2. The evaluation uses only two datasets, which limits how far the results generalize.

Response: We now include a third dataset of long-horizon traces, reported in Table 5.

> 3. The threats to validity section does not discuss selection bias in the benchmark.

Response: We revised Section 5 to discuss selection bias, adding
"Our benchmark tasks were sampled from public repositories."

# Response to Reviewer 2

**R2-W2** There is no ablation of the retrieval component, so its contribution is unknown.

Response: We added an ablation in Table 3, which shows "removing retrieval lowers recall by
twelve points on every dataset".

**R2-Q1** How does the approach scale?

Response: Thank you for this question. We agree.

# Response to the Associate Editor

Response: See our responses to R1.2 for the datasets. We will release the full benchmark in
the camera-ready version.
