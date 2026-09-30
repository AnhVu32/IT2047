# Provenance

Vendored (not a git submodule) from:
https://github.com/aryan-jadon/Evaluation-Metrics-for-Recommendation-Systems
(itself derived from Microsoft's https://github.com/recommenders-team/recommenders,
MIT License), local copy used as source:
`/Users/nguyenvu/Downloads/Evaluation-Metrics-for-Recommendation-Systems-main`.

Only the files needed to import `recommenders.evaluation.python_evaluation`
were copied (its import chain: `numpy`, `pandas`, `scikit-learn`,
`recommenders.utils.constants`, `recommenders.datasets.pandas_df_utils`).
Everything else from the upstream repo (models/, other datasets/, spark
evaluation, docs, experiment scripts) was intentionally left out — this
project only needs the plain-Python metric functions.

Files are unmodified copies (no import rewrites) so `recommenders.*` imports
inside `python_evaluation.py` work unchanged.
