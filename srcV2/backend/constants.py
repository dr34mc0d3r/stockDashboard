"""Named constants shared across the backend.

One home for the numbers that would otherwise hide as unexplained literals in
the middle of the code.
"""

# A sigmoid output at or above this counts as an "up" prediction. 0.5 is the
# natural cut for a balanced binary problem; later stages may tune it.
PROB_THRESHOLD = 0.5

# Early stopping: validation loss must improve by more than this to count as
# progress — guards against "improvements" that are just float noise.
EARLY_STOP_DELTA = 1e-4
