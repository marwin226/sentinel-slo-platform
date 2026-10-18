# ADR 0002 — The AI incident copilot is read-only and evidence-first

**Status:** accepted · **Date:** 2026-10-18

## Context
LLMs are good at summarising and bad at knowing facts they were not given. Letting a model take production
actions during an incident puts a probabilistic system inside the blast radius.

## Decision
1. **Evidence before language.** The copilot first runs fixed PromQL queries (error ratio, p99 and request rate by
   version, burn rate, budget left) and computes the suspect version deterministically. The model only sees that
   evidence plus retrieved runbook sections, and is instructed not to invent numbers.
2. **Read-only.** No Kubernetes service-account token is mounted; it cannot change the cluster. Remediation
   stays with the SLO-gated canary (automatic) and humans (everything else).
3. **Graceful degradation.** Without an API key, or if the LLM call fails, a deterministic brief is produced from
   the same evidence. The LLM is an enhancement, never a dependency.
4. **Auditable.** Every brief embeds the exact PromQL used, so a responder can re-run it.
5. **Vendor-neutral.** Any OpenAI-compatible endpoint works (Groq, OpenAI, Azure OpenAI, vLLM, Ollama).

## Consequences
+ Safe to run in production on day one; useful even with no LLM.
− It recommends rather than fixes; "draft the revert PR" is a roadmap item behind human approval.
