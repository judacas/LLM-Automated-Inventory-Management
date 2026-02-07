# GitHub Repository Settings Recommendations

This document outlines the recommended GitHub repository settings for this team project. These settings cannot be configured automatically and must be set manually through the GitHub web interface.

## Repository Settings

### General Settings

1. **Navigate to**: `Settings > General`

#### Features
- [x] **Issues**: Enable issue tracking
- [x] **Projects**: Enable project boards for task management
- [x] **Wiki**: Optional (consider enabling for comprehensive documentation)
- [x] **Discussions**: Enable for team discussions and Q&A
- [ ] **Sponsorships**: Disable (not needed for student project)

#### Pull Requests
- [x] **Allow merge commits**: Enable
- [x] **Allow squash merging**: Enable (recommended for clean history)
- [x] **Allow rebase merging**: Enable
- [x] **Always suggest updating pull request branches**: Enable
- [x] **Automatically delete head branches**: Enable (keeps repo clean)

## Branch Protection Rules

### Main Branch Protection

1. **Navigate to**: `Settings > Branches > Add rule`
2. **Branch name pattern**: `main`

#### Protection Settings

**Protect matching branches:**
- [x] **Require a pull request before merging**
  - [x] **Require approvals**: 1 (at least one team member must approve)
  - [x] **Dismiss stale pull request approvals when new commits are pushed**
  - [x] **Require review from Code Owners**: Optional (if you create a CODEOWNERS file)

- [x] **Require status checks to pass before merging**
  - [x] **Require branches to be up to date before merging**
  - Required status checks:
    - `Code Quality` (from CI workflow)
    - `Tests` (from CI workflow)

- [x] **Require conversation resolution before merging**
- [ ] **Require signed commits**: Optional (recommended for high-security projects)
- [ ] **Require linear history**: Optional (helps keep history clean)
- [x] **Include administrators**: Recommended to enforce rules for all

**Rules applied to everyone including administrators:**
- [x] **Allow force pushes**: Disable
- [x] **Allow deletions**: Disable

### Development Branch Flexibility

For branches starting with `dev/` or `dev*`:
- No branch protection rules (allows rapid iteration)
- CI checks are automatically skipped
- Use these for experimental work

## Collaborators and Teams

1. **Navigate to**: `Settings > Collaborators and teams`

### Team Members
Add all 5 team members with appropriate permissions:
- **Write access**: All team members should have write access
- **Role**: Choose "Developer" or "Maintainer" for all team members

### External Collaborators
If working with Microsoft sponsors or USF faculty:
- Add them as **Read-only** collaborators
- Or create specific issues/discussions for their feedback

## Security Settings

1. **Navigate to**: `Settings > Security`

### Code Security and Analysis
- [x] **Dependency graph**: Enable (tracks dependencies)
- [x] **Dependabot alerts**: Enable (notifies of vulnerable dependencies)
- [x] **Dependabot security updates**: Enable (auto-creates PRs for security fixes)
- [x] **Dependabot version updates**: Optional (creates PRs for dependency updates)
- [x] **Secret scanning**: Enable (prevents committing secrets)
  - Note: Gitleaks in CI provides additional scanning
- [x] **Code scanning**: Optional (GitHub Advanced Security feature if available)

### Repository Security Advisories
- Consider enabling to privately discuss and fix security vulnerabilities

## Secrets and Variables

1. **Navigate to**: `Settings > Secrets and variables > Actions`

### Repository Secrets
Add any secrets needed for CI/CD:
- `CODECOV_TOKEN` (if using Codecov for coverage reporting)
- Azure credentials (if needed for deployment)
- Any API keys or tokens

**Important**: Never commit secrets to the repository!

## Actions Settings

1. **Navigate to**: `Settings > Actions > General`

### Actions Permissions
- [x] **Allow all actions and reusable workflows**

### Workflow Permissions
- Select: **Read and write permissions**
- [x] **Allow GitHub Actions to create and approve pull requests**: Enable (needed for Dependabot)

## Notifications

### Email Notifications (Per User)
Each team member should configure in their GitHub profile:
- Enable notifications for:
  - Pull request reviews requested
  - Comments on issues and PRs assigned to you
  - @mentions
  - Build failures on your branches

## Projects and Milestones

### Create Projects
1. **Navigate to**: `Projects > New project`
2. Create a project board for the semester:
   - Use "Board" view for Kanban-style workflow
   - Columns: Backlog, To Do, In Progress, Review, Done
   - Add automation rules for moving cards

### Create Milestones
1. **Navigate to**: `Issues > Milestones > New milestone`
2. Create milestones for major deliverables:
   - Sprint 1 (2 weeks)
   - Sprint 2 (2 weeks)
   - Sprint 3 (2 weeks)
   - Mid-semester review
   - Final presentation
   - Final submission

## Labels

### Recommended Labels
Create or ensure these labels exist (`Issues > Labels`):

**Type:**
- `bug` (red) - Something isn't working
- `feature` (green) - New feature or request
- `enhancement` (blue) - Improvement to existing feature
- `documentation` (light blue) - Documentation improvements
- `task` (yellow) - Regular task or chore

**Priority:**
- `priority: high` (red) - Must be done ASAP
- `priority: medium` (orange) - Should be done soon
- `priority: low` (yellow) - Nice to have

**Status:**
- `status: blocked` (red) - Blocked by external factors
- `status: in-progress` (yellow) - Currently being worked on
- `status: needs-review` (blue) - Waiting for code review

**Area:**
- `area: backend` - Backend/API work
- `area: frontend` - Frontend/UI work
- `area: devops` - CI/CD and infrastructure
- `area: testing` - Testing improvements

## Repository Description

Add a clear description at the top of your repository:

**Description**: 
```
AI-powered automated customer service system using Azure AI and multi-agent architecture. A semester-long team project for USF Computer Engineering students.
```

**Topics/Tags**:
- `azure`
- `ai`
- `python`
- `multi-agent`
- `customer-service`
- `mcp`
- `llm`

## README Badge

Add status badges to your README.md:

```markdown
[![CI](https://github.com/judacas/LLM-Automated-Inventory-Management/actions/workflows/ci.yml/badge.svg)](https://github.com/judacas/LLM-Automated-Inventory-Management/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/judacas/LLM-Automated-Inventory-Management/branch/main/graph/badge.svg)](https://codecov.io/gh/judacas/LLM-Automated-Inventory-Management)
```

## CODEOWNERS File (Optional)

Create a `.github/CODEOWNERS` file to automatically request reviews from specific team members:

```
# Default owners for everything in the repo
* @team-member1 @team-member2 @team-member3

# Specific areas (customize based on your team)
/src/agents/ @agent-expert
/docs/ @documentation-lead
/.github/ @devops-lead
```

## Team Workflow Checklist

After configuring the above settings:

- [ ] All team members have been added as collaborators
- [ ] Branch protection rules are enabled on `main`
- [ ] CI status checks are required before merging
- [ ] Pull request templates are working
- [ ] Issue templates are working
- [ ] Project board is set up
- [ ] Milestones are created
- [ ] Labels are configured
- [ ] Notifications are configured for each team member
- [ ] Repository description and topics are set
- [ ] README badges are added (if using external services)

## Additional Resources

- [GitHub Docs: Managing Repositories](https://docs.github.com/en/repositories)
- [GitHub Docs: Branch Protection Rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub Docs: Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects)
