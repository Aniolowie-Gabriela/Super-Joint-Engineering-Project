# Super-Joint-Engineering-Project
AI-powered assistant for Europa Universalis IV, providing game knowledge, strategic advice, and gameplay guidance.

## Agent skills

[taf4you2/agent-skills](https://github.com/taf4you2/agent-skills) is included as a Git submodule in `agent-skills/`.

Clone the project with the submodule:

```bash
git clone --recurse-submodules https://github.com/Aniolowie-Gabriela/Super-Joint-Engineering-Project.git
```

For an existing checkout, fetch the pinned version:

```bash
git submodule update --init --recursive
```

To update to the latest upstream `main`, then record the new version:

```bash
git submodule update --remote agent-skills
git add agent-skills
git commit -m "chore: update agent-skills submodule"
```

See [the agent-skills README](agent-skills/README.md) for skill descriptions and setup instructions.
