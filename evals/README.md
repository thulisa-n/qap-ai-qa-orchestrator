# Prompt evals

Promptfoo grades the Gemini prompts QAP actually sends. The templates live in `app/src/prompts/` and the renderers in `app/src/services/llm_service.py`. This directory does not contain a second copy of the prompt text.

The suite checks:

- scenario JSON shape, including a security case for an auth story
- hallucination on a thin acceptance criterion (no invented routes, selectors, or credentials)
- direct and indirect prompt injection, with Jira acceptance criteria treated as untrusted input
- credential hygiene (`TEST_USER` / `TEST_PASS` only)
- a latency cap (20s) and a cost cap ($0.05) on the login scenario

Those caps are ceilings for Gemini 3.8 Flash, including rubric grading. Tighten them after the first measured run.

The provider is `google:gemini-3.8-flash`. Rubrics use the same model. Set `GEMINI_API_KEY` in the environment. Do not commit it.

```bash
export GEMINI_API_KEY=your_key_here
export PYTHONPATH=.
npm ci --prefix evals
npx --prefix evals promptfoo eval -c evals/promptfooconfig.yaml
```

GitHub Actions job `llm-evals` runs this gate when prompts, agents, or this workflow change. If `GEMINI_API_KEY` is missing, the job skips the live calls and says so. That happens on fork pull requests, which cannot read repository secrets. A static `ai-surface` scan still runs and fails on high findings. Maintainer-branch runs and `workflow_dispatch` are the source of truth once the secret is set.

The red team is intentionally small: three tests each for system-prompt override, hijacking, and hallucination.
