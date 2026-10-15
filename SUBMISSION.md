# Signalpost AI Agent — Submission Information

## Repository
https://github.com/sak55shi/Signalpost-AI-Agent

## Implementation
Python 3.12+ company research agent using official Norwegian company data.

## Setup
uv sync --locked

## Batch execution
python scripts/run_competition_batch.py --organisations entry-companies.jsonl --bulk brreg-enheter.csv --profiles-output out/profiles.jsonl --output out/envelopes.jsonl --report out/run-report.json --run-id submission-001 --expected-count 1000

The organisation batch and registry CSV must be provided before execution. The expected count must match the input batch.

## Verified local test
- 100 companies processed
- 100 terminal envelopes generated
- 558 external requests
- Runtime approximately 4 minutes 25 seconds
- All five validation checks passed
- See smoke-test-report.json

## Refresh verification
Deterministic fixture test:
- 2 expected changes
- 2 detected changes
- No false positives or false negatives
- Evidence complete
- Idempotent rerun passed

This is a local fixture result, not an official evaluation score.

## Sources and APIs
- Bronnoysundregistrene entity registry and associated public APIs
- Norwegian annual accounts API
- Company-reported websites when available

## Models
No LLM or sentiment model is confirmed active in the validated 100-company batch.
Optional sentiment dependencies are defined but not claimed as deployed.

## Licences and source rights
The BRREG entity open-data source is documented under NLOD 2.0.
Other endpoints and company websites remain subject to applicable terms and permissions.
Experimental LinkedIn discovery is not publishable and is not claimed as an active source.

## Expected cost per 100 companies
The validated test used 558 requests.
No paid Brave Search API was configured.
Direct monetary cost was not measured; network, compute, and any applicable third-party charges are excluded.
No zero-cost guarantee is claimed.

## Limitations
Website and group information are not available for every company.
Missing information is reported explicitly rather than invented.
