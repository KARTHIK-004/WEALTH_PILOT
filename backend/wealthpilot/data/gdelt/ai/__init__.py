"""AI-assisted annotation pipeline for the B2 review dataset: BUILT BUT DISABLED.

Nothing in this package calls a model or sends data anywhere. A run needs **all** of:

1. the build lock ``wealthpilot.data.gdelt.AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD`` (``False``);
2. four approval records (A methodology, B provider and model, C data handling, D execution), each bound by
   SHA-256 to exactly what it approves, so approving one thing never approves another;
3. a provider adapter. **None exists:** choosing a provider is Gate B, and writing an adapter for it is a
   separate approved change;
4. an explicit confirmation on the command line.

There is no "enabled" flag, no automatic acceptance policy, and no default provider.

The package reads only the *original* annotation file (which holds no labels) and never reads the human working
copy, the sealed key or any human label. AI suggestions are stored apart from human labels, and a human review
is a separate, audited record that says whether the AI was seen.

The rubric is not changed here: output is validated by the existing rubric validator
(``annotate.content_errors``).
"""

from __future__ import annotations

EXPERIMENT_SCHEMA = "b2t_experiment_v1"
SUGGESTION_SCHEMA = "b2t_ai_suggestion_v1"
REVIEW_SCHEMA = "b2t_review_v1"
DATASET_SCHEMA = "b2t_annotation_v1"
OUTPUT_VERSION = "b2t_ai_output_v1"
