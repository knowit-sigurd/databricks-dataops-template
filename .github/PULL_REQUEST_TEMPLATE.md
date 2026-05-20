## Summary

<!-- What does this PR do and why? Link to any relevant issue or design doc. -->

## Type of change

- [ ] Pipeline logic
- [ ] Bundle config / infrastructure
- [ ] CI/CD
- [ ] Tests
- [ ] Documentation only

## Test plan

- [ ] `make lint` passes
- [ ] `make test` passes
- [ ] PR environment deployed (`make deploy-pr PR_NUMBER=${{ github.event.pull_request.number }}`)
- [ ] Operational job ran successfully in PR environment
- [ ] No regressions in other domains (if pipeline logic changed)

## Checklist

- [ ] Docs updated to reflect current repo state (if applicable)
- [ ] No hardcoded catalog names — `${var.catalog}` used throughout
- [ ] No `import dlt` — `from pyspark import pipelines as dp` only
- [ ] New quality rules cover all three severities (critical / business_invalid / warning)
