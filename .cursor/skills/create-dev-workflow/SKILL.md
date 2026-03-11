---
name: create-dev-workflow
description: Set up a project-level dev-workflow skill that automates the full development cycle from issue to PR/release, with optional quality rules, QA skill, and knowledge directory. Use when the user asks to set up a dev workflow, configure issue tracking, or automate their development process in a project.
---

# Create Dev Workflow

Generate a project-level `.cursor/skills/dev-workflow/SKILL.md` that guides the agent through the full development cycle: issue -> branch -> plan -> implement -> PR -> release.

## Phase 1: Gather Information

### Q1 — Issue tracker

Use AskQuestion:

```
prompt: "Where do you store issues?"
options:
  - GitHub Issues
  - Linear
```

### Q2 — Verify prerequisites

**If GitHub Issues**:
- Run `gh --version` to verify the GitHub CLI is installed
- Run `gh auth status` to verify authentication
- If either fails, instruct the user to install/authenticate `gh` and stop

**If Linear**:
- Check for a Linear MCP server by scanning the mcps folder for a `linear` or `linear-*` server directory
- If not found, instruct the user to configure a Linear MCP server and stop

### Q3 — Release flow detection

1. Scan `.github/workflows/` for files containing `release` triggers (look for `on: release`, `on: push: tags:`, or similar patterns)
2. If found, set `has_release_flow = true`
3. If not found, ask the user:

```
prompt: "This project doesn't appear to have a release workflow. Should the dev workflow include a release step?"
options:
  - Yes, include release step
  - No, skip releases
```

### Q4 — Activation mode

Use AskQuestion:

```
prompt: "How should the dev workflow be activated in new chats?"
options:
  - Always ask — prompt at the start of every new chat
  - Auto-detect — only ask when the conversation looks like dev work
  - No rule — I'll invoke the workflow manually
```

### Q5 — Quality rules

Use AskQuestion:

```
prompt: "Should I also generate quality rules (testing patterns, code review, QA checklist)?"
options:
  - Yes, generate quality rules and QA skill
  - No, just the dev workflow
```

### Q6 — Knowledge directory

Use AskQuestion:

```
prompt: "Should I set up a knowledge directory (AI-facing living docs per feature area)?"
options:
  - Yes, set up knowledge directory
  - No, skip knowledge
```

## Phase 2: Generate the Project Skill

1. Create directory `.cursor/skills/dev-workflow/`
2. Read the appropriate template based on Q1:
   - GitHub Issues: read [templates/github-workflow.md](templates/github-workflow.md)
   - Linear: read [templates/linear-workflow.md](templates/linear-workflow.md)
3. Write the template contents to `.cursor/skills/dev-workflow/SKILL.md`
4. If `has_release_flow` is false, remove the Release step from the generated file before writing
5. If Q4 is **Always ask** or **Auto-detect**, create `.cursor/rules/dev-workflow-activation.mdc` with the matching content below. If Q4 is **No rule**, skip this step.
6. The activation rule content depends on **both Q4 and Q5**. Pick the matching variant below.

---

### Activation rules when Q5 = Yes (quality rules generated)

**Always ask + quality** rule content:

```markdown
---
description: Ask the user at the start of every new chat whether to follow the full development workflow
alwaysApply: true
---

# Chat-Start Triage

At the **very beginning** of every new chat, before doing anything else, use the `AskQuestion` tool:

title: "Chat Mode"
prompt: "Should this chat follow the full development workflow?"
options:
  - id: full
    label: "Yes — full dev workflow (planning, branching, PRs, quality checks)"
  - id: quick
    label: "No — quick task / exploration (skip workflow steps, keep code quality rules)"

## Behavior Based on Answer

**Full dev workflow** (`full`): Read and follow `.cursor/skills/dev-workflow/SKILL.md` strictly — planning before coding, feature branches, incremental commits, PR process. Also enforce all rules from `.cursor/rules/quality.mdc`.

**Quick task / exploration** (`quick`): Skip the structured workflow steps (mandatory planning phase, feature branches, PRs, release process). Still enforce all code quality rules defined in `.cursor/rules/quality.mdc`.
```

**Auto-detect + quality** rule content:

```markdown
---
description: Detect dev-workflow conversations and offer to follow the dev-workflow skill
alwaysApply: true
---

# Chat-Start Triage

At the start of every new conversation, evaluate the user's first message. If it appears to involve development work — such as implementing a feature, fixing a bug, starting a task, working on an issue, or similar engineering activities — use the `AskQuestion` tool:

title: "Chat Mode"
prompt: "This looks like dev work. Which mode should this chat follow?"
options:
  - id: full
    label: "Full dev workflow (planning, branching, PRs, quality checks)"
  - id: quick
    label: "Quick task / exploration (skip workflow steps, keep code quality rules)"

If the conversation is clearly not dev work (questions, docs, config, etc.), do not ask.

## Behavior Based on Answer

**Full dev workflow** (`full`): Read and follow `.cursor/skills/dev-workflow/SKILL.md` strictly — planning before coding, feature branches, incremental commits, PR process. Also enforce all rules from `.cursor/rules/quality.mdc`.

**Quick task / exploration** (`quick`): Skip the structured workflow steps (mandatory planning phase, feature branches, PRs, release process). Still enforce all code quality rules defined in `.cursor/rules/quality.mdc`.
```

---

### Activation rules when Q5 = No (no quality rules)

**Always ask** rule content:

```markdown
---
description: Ask the user at the start of every new chat whether to follow the development workflow
alwaysApply: true
---

# Dev Workflow Activation

At the **very beginning** of every new chat, before doing anything else, use the `AskQuestion` tool:

title: "Dev Workflow"
prompt: "Should this chat follow the dev workflow?"
options:
  - id: yes
    label: "Yes — follow dev workflow (planning, branching, PRs)"
  - id: no
    label: "No — skip workflow"

If the user selects **yes**, read and follow `.cursor/skills/dev-workflow/SKILL.md`.
```

**Auto-detect** rule content:

```markdown
---
description: Detect dev-workflow conversations and offer to follow the dev-workflow skill
alwaysApply: true
---

# Dev Workflow Activation

At the start of every new conversation, evaluate the user's first message. If it appears to involve development work — such as implementing a feature, fixing a bug, starting a task, working on an issue, or similar engineering activities — use the `AskQuestion` tool:

title: "Dev Workflow"
prompt: "This looks like dev work. Should I follow the dev workflow?"
options:
  - id: yes
    label: "Yes — follow dev workflow (planning, branching, PRs)"
  - id: no
    label: "No — skip workflow"

If the user selects **yes**, read and follow `.cursor/skills/dev-workflow/SKILL.md`.
If the conversation is clearly not dev work (questions, docs, config, etc.), do not ask.
```

---

### Quality artifacts (Q5 = Yes only)

If Q5 is **Yes**, generate the following additional files. If Q5 is **No**, skip this section entirely.

7. Read [templates/quality-rule.md](templates/quality-rule.md) and write it to `.cursor/rules/quality.mdc`
8. Create directory `.cursor/skills/quality-assurance/`
9. Read [templates/quality-assurance.md](templates/quality-assurance.md) and write it to `.cursor/skills/quality-assurance/SKILL.md`

---

### Knowledge artifacts (Q6 = Yes only)

If Q6 is **Yes**, generate the following additional files. If Q6 is **No**, skip this section entirely.

10. Read [templates/knowledge-rule.md](templates/knowledge-rule.md) and write it to `.cursor/rules/knowledge.mdc`
11. Create directory `knowledge/`
12. Read [templates/knowledge-architecture.md](templates/knowledge-architecture.md) and write it to `knowledge/architecture.md`
13. Create directory `.cursor/skills/knowledge-management/`
14. Read [templates/knowledge-management.md](templates/knowledge-management.md) and write it to `.cursor/skills/knowledge-management/SKILL.md`
15. The workflow templates contain a knowledge step wrapped in `<!-- KNOWLEDGE STEP start -->` / `<!-- KNOWLEDGE STEP end -->` markers. If Q6 is **No**, remove everything between (and including) these markers from the generated file, then renumber the subsequent steps to close the gap. If Q6 is **Yes**, remove only the marker comments and keep the step content.

## Phase 3: Confirm

Tell the user:
- The dev-workflow skill has been created at `.cursor/skills/dev-workflow/SKILL.md`
- It will trigger when they say things like "let's work on a feature", "fix a bug", or "start a dev task"
- Mention which issue tracker is configured
- Mention whether the release step is included
- Mention the activation mode: **Always ask** (rule created, will prompt every chat), **Auto-detect** (rule created, will prompt when it looks like dev work), or **No rule** (manual invocation only)
- If Q5 was **Yes**, also mention:
  - Quality rules have been created at `.cursor/rules/quality.mdc` (always active, enforced in both full and quick modes)
  - QA skill has been created at `.cursor/skills/quality-assurance/SKILL.md` (can be invoked explicitly with "run QA")
- If Q6 was **Yes**, also mention:
  - Knowledge conventions rule has been created at `.cursor/rules/knowledge.mdc` (always active, guides the agent on reading/writing knowledge files)
  - An initial `knowledge/architecture.md` skeleton has been created for them to fill in
  - Knowledge management skill has been created at `.cursor/skills/knowledge-management/SKILL.md` (can be invoked with "update knowledge" or "create knowledge file for X")
  - The dev workflow includes an "Update Knowledge" step before the PR step
