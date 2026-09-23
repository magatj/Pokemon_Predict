## What changed

<!-- One or two sentences. -->

## Why

<!-- The problem this solves. -->

## Checks

- [ ] `ruff check .`
- [ ] `pytest`
- [ ] `npm run lint`
- [ ] `npm run test`
- [ ] `npm run build`
- [ ] `terraform fmt -check -recursive infrastructure/terraform`

## If this touches forecasting or a data source

- [ ] No fabricated probabilities: a machine below `minimum_observations` still
      reports `INSUFFICIENT_DATA` or a clearly-labelled `NETWORK_PATTERN`
- [ ] Network-level figures are never presented as machine-specific
- [ ] New sources respect robots.txt, rate limits and HTTP caching, and log
      `SOURCE_SKIPPED` rather than working around a refusal
- [ ] Parser changes are covered by a fixture test, including malformed input
