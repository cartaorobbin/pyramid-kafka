---
name: dev-workflow
description: Automate the full development cycle from issue to pull request using Linear. Use when the user wants to work on a feature, fix a bug, start a dev task, or says things like "let's work on", "implement", or "fix".
---

# Dev Workflow (Linear)

Guide the developer through the full cycle: issue -> branch -> plan -> implement -> PR -> release.

This workflow uses Linear MCP tools for issue tracking and `gh` CLI for pull requests and releases.

## Step 1: Issue

Use AskQuestion:

```
prompt: "Do you already have a Linear issue for this work?"
options:
  - Yes, I have an issue URL or identifier
  - No, let's create one
```

### If the user has an issue

Ask for the issue URL or identifier (e.g., `TEAM-123`). Fetch the issue details using the Linear MCP:

```
CallMcpTool: server=linear, toolName=getIssue
arguments: { "id": "<issue-id>" }
```

Parse the title, description, labels, and team key for context.

### If the user does not have an issue

Discuss the work with the user to define:
- **Title**: concise summary
- **Description**: what needs to happen and why
- **Labels**: bug, feature, improvement, etc.
- **Team**: which Linear team this belongs to

When the issue is well-defined, create it using the Linear MCP:

```
CallMcpTool: server=linear, toolName=createIssue
arguments: { "title": "<title>", "description": "<description>", "teamId": "<team-id>", "labelIds": ["<label-id>"] }
```

Capture the issue identifier from the response.

## Step 2: Branch

Determine the branch type from labels or context:
- `bug` label -> `fix/`
- `feature` or `improvement` label -> `feat/`
- otherwise -> `task/`

Create a slug from the issue title (lowercase, hyphens, max 40 chars).

```bash
git checkout -b <type>/<issue-identifier>-<slug>
git push -u origin HEAD
```

Example: `fix/TEAM-123-login-timeout`

Linear's GitHub integration auto-links branches matching the `TEAM-NNN` pattern.

## Step 3: Plan

Tell the user: "Switching to plan mode to design the implementation."

Use the SwitchMode tool to enter plan mode. Then create an implementation plan by:
1. Reading the issue description
2. Exploring the relevant parts of the codebase
3. Drafting a step-by-step plan with specific files and changes

The plan should include:
- A summary of the approach
- Ordered list of tasks (each should be a concrete, testable unit of work)
- Files to create or modify per task
- Test strategy

Wait for the user to review and approve the plan.

## Step 4: Store Plan

Once the plan is approved:

1. Post the plan as a comment on the Linear issue:

```
CallMcpTool: server=linear, toolName=createComment
arguments: { "issueId": "<issue-id>", "body": "## Implementation Plan\n\n<the approved plan>" }
```

2. Update the issue status to "In Progress":

```
CallMcpTool: server=linear, toolName=updateIssue
arguments: { "id": "<issue-id>", "stateId": "<in-progress-state-id>" }
```

3. Create TodoWrite entries for each task in the plan. Set the first task to `in_progress`, the rest to `pending`.

## Step 5: Execute

Switch back to agent mode using the SwitchMode tool.

Work through the tasks sequentially:
1. Pick the current `in_progress` task
2. Implement the changes
3. Run tests if applicable
4. Mark the task as `completed` in TodoWrite
5. Move the next task to `in_progress`

After completing each task, post a progress comment on the Linear issue:

```
CallMcpTool: server=linear, toolName=createComment
arguments: { "issueId": "<issue-id>", "body": "Completed: <task description>" }
```

## Step 6: Sync

Throughout execution, keep the Linear issue and TodoWrite aligned:
- When a task is completed locally, comment on the issue
- If the plan needs adjustment mid-execution, update both the TodoWrite list and post an updated plan comment on the issue
- If new tasks emerge, add them to both TodoWrite and the issue

<!-- KNOWLEDGE STEP start -->
## Step 7: Update Knowledge

Before creating the PR, update the project's knowledge files:

1. Check if the changes affect a feature area that has an existing `knowledge/*.md` file — if so, read the file and update any sections that are now stale. Rewrite sections to reflect the current state rather than appending notes.
2. If a new feature area was introduced and no knowledge file exists, create one following the structure in `.cursor/rules/knowledge.mdc` (Overview, Design Decisions, API Surface, Key Learnings / Gotchas).
3. If the changes affect the overall architecture, update `knowledge/architecture.md`.
4. Commit knowledge updates separately:

```bash
git add knowledge/
git commit -m "docs: update knowledge for <feature>"
```
<!-- KNOWLEDGE STEP end -->

## Step 8: Pull Request

When all tasks are complete:

1. Ensure all changes are committed
2. Push the branch: `git push`
3. Create the PR using `gh` CLI:

```bash
gh pr create --title "<issue-title>" --body "$(cat <<'EOF'
## Summary
<1-3 bullet points describing what was done>

Resolves <TEAM-NNN>

## Test plan
<checklist of how to verify the changes>

EOF
)"
```

4. Update the Linear issue status to "In Review":

```
CallMcpTool: server=linear, toolName=updateIssue
arguments: { "id": "<issue-id>", "stateId": "<in-review-state-id>" }
```

5. Tell the user the PR is ready for review and provide the PR URL.

## Step 9: Release

> This step only applies to projects with a release flow.

After the PR is merged:

1. Update the Linear issue status to "Done":

```
CallMcpTool: server=linear, toolName=updateIssue
arguments: { "id": "<issue-id>", "stateId": "<done-state-id>" }
```

2. Detect the latest release tag:

```bash
gh release list --limit 1
```

3. Determine the next version using semantic versioning:
   - Bug fix -> patch bump (1.0.0 -> 1.0.1)
   - Feature -> minor bump (1.0.0 -> 1.1.0)
   - Breaking change -> major bump (1.0.0 -> 2.0.0)

   Use the issue labels and nature of changes to decide.

4. Create the release:

```bash
gh release create v<version> --generate-notes --title "v<version>"
```

5. Tell the user the release has been created and provide the URL.

## Step 10: End

Summarize what was accomplished:
- Linear issue identifier and title
- Branch name
- Number of commits
- PR URL
- Release version (if applicable)

Update the Linear issue status to "Done" if not already done:

```
CallMcpTool: server=linear, toolName=updateIssue
arguments: { "id": "<issue-id>", "stateId": "<done-state-id>" }
```
