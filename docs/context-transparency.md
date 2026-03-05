# Context Transparency in AI Launcher

## Overview

When Claude Code starts a session, it loads context from **multiple sources**. The AI Launcher's **Startup Report** feature makes this process transparent, helping users understand exactly what Claude knows about their project and how to optimize their experience.

## Context Sources

### 1. Project Instructions (CLAUDE.md)
**Location:** `<project-root>/CLAUDE.md`
**Purpose:** Project-specific rules, architecture, and development conventions
**Always loaded:** ✅ Yes, if present
**Official docs:** https://code.claude.com/docs/en/claude-md

**What it is:**
- Instructions **you write** for Claude
- Project-specific rules and patterns
- Architecture decisions and conventions
- Links to other documentation

**Best practices:**
- Keep it concise (under 500 lines)
- Move detailed docs to separate files
- Use it for "rules" not "knowledge"
- Link to other context files

**Example:**
```markdown
# My Project - Claude Guide

## Code Style
- Use TypeScript strict mode
- Prefer functional components (React)
- Test coverage minimum: 80%

## Architecture
- API: `/src/api` (Express)
- Frontend: `/src/components` (React)
- Database: PostgreSQL with Prisma ORM

## See also
- [API Documentation](docs/API.md)
- [Database Schema](docs/SCHEMA.md)
```

---

### 2. Auto Memory (MEMORY.md)
**Location:** `~/.claude/projects/<encoded-project-path>/memory/MEMORY.md`
**Purpose:** Claude's persistent learnings across sessions
**Always loaded:** ✅ Yes (first 200 lines only)
**Official docs:** https://code.claude.com/docs/en/memory

**What it is:**
- Notes **Claude writes** for itself
- Bugs encountered and fixes applied
- Project patterns discovered
- Mistakes to avoid
- Commands that work

**Path encoding:**
- `/home/user/my_project` → `-home-user-my-project`
- Both `/` and `_` convert to `-`
- Example: `/home/kwschulz/projects/solentlabs/network-monitoring/cable_modem_monitor`
  - Becomes: `-home-kwschulz-projects-solentlabs-network-monitoring-cable-modem-monitor`

**The 200-line limit:**
- Only first 200 lines load into Claude's context
- Keep MEMORY.md as an **index**
- Move detailed notes to topic files:
  - `debugging.md` - debugging techniques
  - `patterns.md` - code patterns
  - `gotchas.md` - common mistakes

**Best practices:**
- Let Claude manage it automatically
- Tell Claude to remember things: *"Remember we use pytest for testing"*
- Review periodically and remove outdated info
- Create topic files when approaching 200 lines

**Example MEMORY.md:**
```markdown
# My Project - Auto Memory

## Bug #42: Race condition in API endpoint (2026-02-01)
Fixed by adding mutex lock. See `patterns.md#concurrency` for details.

## Testing
- Always run `npm test` before pushing
- Integration tests require Docker running
- Coverage minimum: 80%

## Database
- Use migrations for schema changes: `npm run migrate`
- Never edit schema.prisma directly in production

## Deployment
- Staging: `npm run deploy:staging`
- Production requires manual approval

See also:
- [Debugging Guide](debugging.md)
- [Common Patterns](patterns.md)
```

---

### 3. Global Settings
**Location:** `~/.claude/settings.json`
**Purpose:** Global Claude preferences (model selection, features)
**Always loaded:** ✅ Yes
**Official docs:** https://code.claude.com/docs/en/settings

**What it is:**
- Your global Claude Code preferences
- Model selection (sonnet/opus/haiku)
- Feature flags

**Example:**
```json
{
  "model": "sonnet",
  "fastMode": false
}
```

---

### 4. Project Settings Override
**Location:** `<project-root>/.claude/settings.local.json`
**Purpose:** Override global settings for specific projects
**Always loaded:** ✅ Yes, if present
**Official docs:** https://code.claude.com/docs/en/settings

**What it is:**
- Project-specific setting overrides
- Can override model, features, etc.
- Takes precedence over global settings

**Example:**
```json
{
  "model": "opus",
  "comment": "Use Opus for this complex codebase"
}
```

**When to use:**
- Large codebases (use Opus)
- Simple projects (use Haiku for speed)
- Projects with specific requirements

---

### 5. Git Context
**Location:** `<project-root>/.git/`
**Purpose:** Branch name, git status, recent commits
**Always loaded:** ✅ Yes, if git repo
**Official docs:** https://git-scm.com/doc

**What Claude sees:**
- Current branch name
- Modified/staged files
- Recent commit messages
- Git configuration

---

## AI Launcher Integration

### The Startup Report Feature

The AI Launcher provides transparency into what context is loaded when you start a Claude Code session.

#### Startup Report

When you select a project, AI Launcher automatically displays a context summary before launching Claude Code.

**Example output:**
```
┌─────────────────────────────────────────────────────────────────┐
│  Claude Code Startup Context Report                            │
│  Transparency: What Context is Claude Loading?                 │
└─────────────────────────────────────────────────────────────────┘

📁 Project: /home/user/my-app

1. Project Instructions (CLAUDE.md)
   Status: loaded
   Path: /home/user/my-app/CLAUDE.md
   Size: 7.8 KB
   Lines: 204
   Purpose: Project-specific rules, architecture, and conventions
   📚 Docs: https://code.claude.com/docs/en/claude-md

2. Auto Memory (MEMORY.md)
   Status: loaded
   Path: ~/.claude/projects/-home-user-my-app/memory/MEMORY.md
   Size: 2.1 KB
   Lines: 48
   Purpose: Claude's persistent learnings across sessions
   📚 Docs: https://code.claude.com/docs/en/memory

   ✅ Good - concise and focused

3. Global Settings
   Status: loaded (model: sonnet)
   Path: ~/.claude/settings.json
   Purpose: Global Claude preferences
   📚 Docs: https://code.claude.com/docs/en/settings

   ✅ Global preferences loaded

4. Project Settings Override
   Status: not present
   Purpose: Project-specific overrides for global settings
   📚 Docs: https://code.claude.com/docs/en/settings

   💡 Create .claude/settings.local.json to override global settings

5. Git Context
   Status: loaded
   Path: /home/user/my-app/.git
   Purpose: Branch name, git status, recent commits
   📚 Docs: https://git-scm.com/doc

   ✅ Git branch, status, and recent commits available

─────────────────────────────────────────────────────────────────

💡 Tips for Maximizing Your Experience:

   1. Keep CLAUDE.md concise - move detailed docs elsewhere
   2. Let auto memory grow naturally - Claude learns as you work
   3. Use project settings to override model/preferences per-project
   4. Tell Claude to remember things: 'Remember we use pytest'

📖 Learn more:
   • CLAUDE.md guide: https://code.claude.com/docs/en/claude-md
   • Auto memory: https://code.claude.com/docs/en/memory
   • Settings: https://code.claude.com/docs/en/settings
```

#### Summary Mode

A compact summary is also shown at launch:

```
═══════════════════════════════════════════════════════════════
  CONTEXT LOADED FOR THIS SESSION
═══════════════════════════════════════════════════════════════

✅ Project Instructions (CLAUDE.md): loaded
✅ Auto Memory (MEMORY.md): loaded (48 lines)
✅ Global Settings: loaded (model: sonnet)
⚪ Project Settings Override: not present
✅ Git Context: loaded
═══════════════════════════════════════════════════════════════
```

---

## Tips for Maximizing Your Experience

### 1. Start with CLAUDE.md
Create a basic project guide:
```bash
# In your project root
cat > CLAUDE.md << 'EOF'
# My Project - Claude Guide

## Quick Start
npm install && npm run dev

## Code Style
- TypeScript strict mode
- ESLint + Prettier
- Test coverage: 80% minimum

## Architecture
- API: Express + Prisma
- Frontend: React + TailwindCSS
- Tests: Jest + React Testing Library

## Important Commands
- `npm test` - Run tests
- `npm run migrate` - Run database migrations
- `npm run build` - Production build
EOF
```

### 2. Let Auto Memory Grow Naturally
Don't manually edit MEMORY.md. Instead, tell Claude to remember things:

**During a session:**
```
You: "Remember that we always run 'npm test' before pushing"
Claude: "I'll remember that..."
# Claude adds it to MEMORY.md automatically
```

### 3. Use Project Settings for Special Cases
Override model for specific projects:

```bash
# Large, complex codebase - use Opus
mkdir -p .claude
cat > .claude/settings.local.json << 'EOF'
{
  "model": "opus",
  "comment": "Complex codebase needs Opus"
}
EOF

# Simple utility - use Haiku for speed
cat > .claude/settings.local.json << 'EOF'
{
  "model": "haiku",
  "comment": "Simple project, optimize for speed"
}
EOF
```

### 4. Review Auto Memory Periodically
Check what Claude has learned:
```bash
# View your auto memory
cat ~/.claude/projects/-home-user-my-app/memory/MEMORY.md

# If it's getting long, ask Claude to reorganize:
"Review MEMORY.md and move detailed notes to topic files"
```

### 5. Review Context Before Important Work

Launch AI Launcher and review the startup report to verify context is loaded correctly before starting critical work:
```bash
ai-launcher claude ~/projects
```

---

## Official Documentation Links

### Claude Code Documentation
- **Main docs:** https://code.claude.com/docs
- **CLAUDE.md guide:** https://code.claude.com/docs/en/claude-md
- **Auto memory:** https://code.claude.com/docs/en/memory
- **Settings:** https://code.claude.com/docs/en/settings
- **Setup guide:** https://code.claude.com/docs/en/setup

### Community Resources
- **Persistent Memory Guide:** https://agentnativedev.medium.com/persistent-memory-for-claude-code-never-lose-context-setup-guide-2cb6c7f92c58
- **Memory Deep Dive:** https://therealjasoncoleman.com/2026/02/05/giving-claude-code-a-memory-and-a-soul-with-automem/
- **Claude API Memory Tool:** https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool

---

## FAQ

### Q: Why doesn't Claude remember things from previous sessions?
**A:** Check if auto memory is enabled:
```bash
# Enable auto memory
export CLAUDE_CODE_DISABLE_AUTO_MEMORY=0

# Verify memory file exists
ls -la ~/.claude/projects/-*/memory/MEMORY.md
```

### Q: My MEMORY.md is over 200 lines. What now?
**A:** Only the first 200 lines load automatically. Options:
1. Keep MEMORY.md as an index with links to topic files
2. Ask Claude to reorganize: *"Move detailed notes to topic files"*
3. Review and remove outdated entries

### Q: Should I manually edit MEMORY.md?
**A:** You can, but it's better to let Claude manage it. Tell Claude what to remember:
- *"Remember that tests require Docker running"*
- *"Save to memory: API key is in .env.local"*

### Q: Can I have different CLAUDE.md files for different branches?
**A:** No, CLAUDE.md is checked into git and shared across branches. Use comments for branch-specific info:
```markdown
## Branch-Specific Notes
- `main` branch: Production-ready code
- `develop` branch: Integration testing
- `feature/*` branches: Experimental features
```

### Q: How do I share auto memory across my team?
**A:** Auto memory is **local-only** by design (privacy-first). To share knowledge:
1. Use CLAUDE.md (checked into git)
2. Convert important memories to documentation
3. Use shared context (see Layered Context Architecture in CLAUDE.md)

### Q: What's the difference between CLAUDE.md and MEMORY.md?
- **CLAUDE.md:** Instructions **you write** for Claude (project rules)
- **MEMORY.md:** Notes **Claude writes** for itself (lessons learned)

Think of CLAUDE.md as "the manual" and MEMORY.md as "the journal".

---

## Next Steps

1. ✅ **Check your context:** Launch a project and review the startup report
2. ✅ **Create CLAUDE.md:** Add project-specific rules
3. ✅ **Let memory grow:** Tell Claude to remember important things
4. ✅ **Review periodically:** Keep context fresh and relevant
5. ✅ **Share knowledge:** Convert learnings to team documentation

---

**Made by Solent Labs™** - Building tools for developers who value transparency and local-first software.
