# Safety & Approval System

## Philosophy

AI Workbench operates on a principle of minimal trust. Agents can read and analyze code freely, but any action that modifies the system, installs software, or communicates externally must be explicitly approved by the human operator.

## Approval-Required Actions

The following actions always require human approval before execution:

| Action | Pattern | Risk |
|--------|---------|------|
| File deletion | `rm -rf`, `rm -r` | Data loss |
| Git push | `git push`, `git push --force` | Code publication |
| Package install | `pip install`, `npm install -g`, `brew install` | System modification |
| Docker teardown | `docker compose down -v`, `docker system prune` | Data loss |
| Environment modification | `.env` file changes | Credential exposure |
| Elevated execution | `sudo`, piped `curl\|sh` | System compromise |
| Package publish | `npm publish` | Public release |

## How It Works

1. An agent attempts a restricted action
2. The safety layer detects the action via pattern matching
3. An `ApprovalRequest` is created with details of the command
4. The agent run enters `waiting_approval` status
5. The user sees the request in the Approvals panel
6. The user approves or rejects
7. If approved, the agent proceeds. If rejected, the agent must find an alternative.

## Configuration

Safety rules are defined in `config.yaml` under the `safety` key. The list of restricted actions can be customized.

## Principles

- **Default deny**: If in doubt, require approval
- **Transparency**: Every action is logged
- **No silent execution**: Agents never run restricted commands silently
- **Reversibility**: Prefer reversible actions over destructive ones
- **Least privilege**: Agents operate with minimal required permissions
