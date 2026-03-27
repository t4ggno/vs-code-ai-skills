# VS Code AI Skills

A collection of AI skills and tools for VS Code Copilot.

## What are VS Code Agent Skills?

Agent Skills are localized folders containing instructions, scripts, and resources that GitHub Copilot can dynamically load to perform specialized tasks. Agent Skills follow an open standard (agentskills.io) and work seamlessly across multiple AI agents, including GitHub Copilot in VS Code, the GitHub Copilot CLI, and the Copilot coding agent.

Unlike standard custom instructions—which are primarily used to define persistent coding guidelines or project-specific standards—Agent Skills enable highly-specialized workflows. Whenever a user requests a task that matches a skill's domain, Copilot can automatically invoke the skill's specific instructions, execute its scripts, or load its resources without cluttering the master context with unrelated files.

### Key Benefits of Agent Skills

- **Specialize Copilot:** Tailor Copilot capabilities for domain-specific tasks without needing to repeat context manually.
- **Reduce Repetition:** Configure a skill once and use it automatically across all conversations.
- **Efficient Context Loading:** Skills are loaded strictly on-demand. Only relevant content is brought into context when needed.
- **Compose Capabilities:** Combine multiple skills to build complex, specialized workflows (e.g., testing, debugging, image generation, or deployment processes).
- **Portability:** Designed using an open standard, allowing skills to be shared and utilized across any skills-compatible agent format.

## Skill Locations & Project Structure

Agent Skills are organized as individual directories. Each directory represents a primary skill and must contain a `SKILL.md` file that defines its behavior and instructions.

Depending on their scope, skills should be located in one of two places:

1. **Personal Skills (Global) - Windows Default**  
   These are stored in your home directory and are automatically available globally across all your projects in VS Code.  
   **Location:** `C:\Users\<USERNAME>\.copilot\skills` (or `~/.copilot/skills` on macOS/Linux).
2. **Project Skills (Local)**  
   These are tracked inside a specific repository only and run exclusively when working in that project.  
   **Location:** `.github/skills` inside the top-level project root directory.

### Example Structure for this Repository

This repository models the layout of your **Personal Skills** directory (`.copilot/skills`):

```text
.copilot/skills/
├── README.md                      # This documentation
├── image-generator/               # Image generation skill
│   ├── SKILL.md
│   └── generate.py
├── math-calculator/               # Math calculation skill
│   ├── SKILL.md
│   └── calculate.py
├── pdf-text-extractor/            # PDF text extraction skill
│   ├── SKILL.md
│   └── extract.py
├── system-info/                   # Hardware/OS info skill
│   ├── SKILL.md
│   └── info.py
├── uuid-generator/                # UUID generation skill
│   ├── SKILL.md
│   └── generate.py
└── web-scraper/                   # Simple web scraper skill
    ├── SKILL.md
    └── fetch.py
```

## How to Install and Use

1. Clone or download this repository.
2. Place the contents directly into your global skills directory at:
   `C:\Users\<USERNAME>\.copilot\skills`
   _(Replace `<USERNAME>` with your Windows user profile name)._
3. Restart or reload GitHub Copilot in VS Code.
4. The next time you invoke Copilot in chat (e.g., _"Generate an image of a futuristic server farm"_), it will evaluate your request against the loaded `SKILL.md` profiles and automatically invoke the matching skill's workflow.
