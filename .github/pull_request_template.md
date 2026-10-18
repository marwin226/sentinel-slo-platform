## What & why

## Reliability checklist
- [ ] SLO impact considered (does this change an SLI, a dependency, or capacity?)
- [ ] New alerts have a runbook section in `docs/runbooks/`
- [ ] Rollback is a `git revert` (no manual cluster changes)
- [ ] `make check` passes locally
