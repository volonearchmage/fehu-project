# v2 prospective revision

Protocol commit d9d070ba1290c30520f8a56c053fb753fe30e956. Read using git show after fetching origin/main; research branch and local HEAD preserved.

The old 8-bag/100-update diagnostic did not pass its frozen Recall criterion. Its files and checkpoints are unchanged; v2 removes that uncalibrated prerequisite prospectively and does not relabel it as passed. All T/J/S complete three epochs unless a real engineering fault occurs.

T retains the exact full context, pooling and shared 108-head of J/S, with article loss weight zero. J/S retain v1 loss definitions and normalization. Input v2 removes interpolated actor ID and event ID, keeping semantic text and article-local numbering. This is a controlled preprocessing change, not evidence that IDs caused the earlier low recall. Only fit/tune caches are rebuilt.

All original token spans and event candidates are preserved. Body windows retain max8192/overlap256, earliest ownership and ownership-weighted vector aggregation; one head application and supervision per original bag/event. The unique long bag is now 9585 tokens, windows8192/1985 (previous9641,8192/2097); all9 events remain.

All methods use exact tune global threshold scanning (score>=threshold, tied-score groups, empty threshold2.0), higher threshold then earlier epoch ties. P uses the selected J epoch, no independent training or epoch search. No holdout/DEV/TEST scores in this pilot.

Engineering checks target changed input/T/threshold/restore mechanics only. Existing CUDA recovery and v1 GPU acceptance remain historical evidence; a newly executed receipt binds v2 code and inputs.
