# FEHU Project State

This repository contains the FEHU / NTCIR-19 Task-1 project, including research code and output folders for transfer and reproducibility.

Current latest stage:
- DRA-FEHU tiny pilot completed.
- AI-assisted verification completed.
- Human decisions completed.
- Verified candidate pool created.
- Latest verified candidate folder:
  ntcir19_fehu-master/output/research_verified_candidates/20260702_132154/
- Verified candidates: 5
- Rejected candidates: 1
- L1=38 Be honest direction-contrastive pair: COMPLETE
- L1=12 Have success direction-contrastive pair: INCOMPLETE
- No training or ablation has been run after verified candidate creation.

Important safety note:
- output/ is included for transfer and audit.
- Do not treat all output files as training input.
- Future training or ablation should only use explicitly selected verified candidate files.
- The rejected L1=12 Have success contradictory candidate must not be used for training.
- API keys and .env files must not be committed.
