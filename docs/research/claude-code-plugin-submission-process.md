# Research: Claude Code Plugin Submission to Anthropic's Official Plugin Directory

**Date**: 2026-03-03 (updated) | **Original**: 2026-02-28 | **Researcher**: nw-researcher (Nova) | **Confidence**: High | **Sources**: 12

## Executive Summary

Anthropic operates an **official curated plugin directory** (`claude-plugins-official`) that is automatically available to all Claude Code users. Third-party developers can submit plugins for inclusion via a **Google Form** at `clau.de/plugin-directory-submission` or through **in-app submission forms** at `claude.ai/settings/plugins/submit` (Claude.ai) and `platform.claude.com/plugins/submit` (Console). Submission does not guarantee inclusion -- Anthropic performs both automated and manual review.

The directory has a two-tier structure: `/plugins` for Anthropic-maintained internal plugins (~25 plugins) and `/external_plugins` for approved third-party submissions (~13 plugins as of 2026-02-28). External plugins that pass review are added to the repository and listed in the central `marketplace.json` catalog. Plugins with an **"Anthropic Verified" badge** have undergone additional quality and safety review beyond the basic automated screening.

Anthropic enforces specific policies through their **Software Directory Policy** and **Software Directory Terms**, which require developers to comply with safety/security standards, provide accurate documentation, maintain a privacy policy, supply test accounts and working examples, and accept indemnification obligations. Direct pull requests to the repository from external contributors are **automatically closed** by CI automation -- the submission form is the only approved channel.

## Research Methodology

**Search Strategy**: Official Anthropic documentation (code.claude.com), Anthropic GitHub repositories (anthropics/claude-plugins-official, anthropics/claude-code), Anthropic Help Center (support.claude.com), plugin submission form (Google Forms), official blog posts, and web search for community context. Updated 2026-03-03 with detailed technical specifications from plugins-reference, marketplace schema, and expanded plugin.json manifest documentation.
**Source Selection**: Types: official docs, official repositories, official policy documents | Reputation: high (1.0) minimum for all primary claims | Verification: cross-referencing across official sources.
**Quality Standards**: Min 3 sources/claim | All major claims cross-referenced | Avg reputation: 0.97

## Findings

### Finding 1: Three Submission Channels Exist

**Evidence**: The official documentation at code.claude.com states: "The official marketplace is maintained by Anthropic. To submit a plugin to the official marketplace, use one of the in-app submission forms: Claude.ai: claude.ai/settings/plugins/submit, Console: platform.claude.com/plugins/submit." The claude-plugins-official README additionally directs to the plugin directory submission form at `clau.de/plugin-directory-submission`, which resolves to a Google Form.
**Source**: [Discover and Install Plugins - Claude Code Docs](https://code.claude.com/docs/en/discover-plugins) - Accessed 2026-02-28
**Confidence**: High
**Verification**: [claude-plugins-official README](https://github.com/anthropics/claude-plugins-official/blob/main/README.md), [Claude Plugin Submission Form](https://docs.google.com/forms/d/e/1FAIpQLSc31jdYDs_1z649BmFfX85mSSdyTXi0GOLsHD7tWKj0F_k9Dg/viewform)
**Analysis**: There are three entry points that likely converge to the same review pipeline: (1) in-app form via Claude.ai, (2) in-app form via Console, and (3) the standalone Google Form. The Google Form is the one explicitly linked from the GitHub repository README.

### Finding 2: Submission Form Requirements

**Evidence**: The Google Form titled "Claude Plugin Submission Form" requires the following fields:
- **Plugin Name** (required) -- name as it will appear in directory
- **Plugin Description** (required) -- 50-100 words describing capabilities
- **Target Platform** (required) -- Claude Code, Cowork, or Both
- **GitHub Repository Link** (required/preferred) -- top-level git repository
- **Hosted File Link** (optional alternative) -- compressed plugin folder via public download
- **Company/Organization URL** (required)
- **Primary Contact Email** (required) -- for review correspondence
- **Plugin Examples** (required) -- minimum three use cases for public directory display

The form states: "All submissions to this form will be reviewed for inclusion in the plugin marketplace. Please note that submitting this form does not guarantee inclusion."
**Source**: [Claude Plugin Submission Form](https://docs.google.com/forms/d/e/1FAIpQLSc31jdYDs_1z649BmFfX85mSSdyTXi0GOLsHD7tWKj0F_k9Dg/viewform) - Accessed 2026-02-28
**Confidence**: High
**Verification**: [claude-plugins-official README](https://github.com/anthropics/claude-plugins-official/blob/main/README.md), [Anthropic Software Directory Policy](https://support.claude.com/en/articles/13145358-anthropic-software-directory-policy)
**Analysis**: The form is straightforward. GitHub is the preferred distribution mechanism. A company/organization URL is required, which may disadvantage individual developers without an organizational identity. The three-example requirement aligns with the Software Directory Policy's testing requirements.

### Finding 3: Two-Tier Review Process (Basic vs Anthropic Verified)

**Evidence**: The official plugin directory page at claude.com/plugins displays an "Anthropic Verified" badge on select plugins. The directory documentation states: "Anthropic performs basic automated review on submissions before adding them to the directory, and plugins with an 'Anthropic Verified' badge have undergone additional review from a quality and safety perspective." The Software Directory Policy adds: "Anthropic reviews submissions to its Directories to ensure they meet standards for safety, security, and compatibility, conducting both initial and ongoing reviews of software."
**Source**: [Plugins for Claude Code and Cowork](https://claude.com/plugins) - Accessed 2026-02-28
**Confidence**: High
**Verification**: [Anthropic Software Directory Policy](https://support.claude.com/en/articles/13145358-anthropic-software-directory-policy), [claude-plugins-official README](https://github.com/anthropics/claude-plugins-official/blob/main/README.md), [Discover Plugins Docs](https://code.claude.com/docs/en/discover-plugins)
**Analysis**: There are two levels of trust: (1) basic automated review for all submissions -- necessary to be listed, and (2) "Anthropic Verified" badge for plugins that pass additional manual quality and safety review. Plugins without the badge are still listed but with an implicit lower trust signal.

### Finding 4: Software Directory Policy -- Detailed Requirements

**Evidence**: The Anthropic Software Directory Policy at support.claude.com specifies comprehensive requirements:

**Developer obligations:**
- Provide a clear, accessible privacy policy link
- Verified contact information and support channels
- Document functionality, purpose, and troubleshooting guidance
- Furnish a standard testing account with sample data for Anthropic to verify functionality
- Deliver at least three working examples of prompts/use cases
- Verify ownership/control of all API endpoints, domains, and UIs the software connects to
- Maintain software and address issues within reasonable timeframes
- Accept Software Directory Terms and design guidelines

**Safety and security requirements -- software must not:**
- Violate Anthropic's Usage Policy
- Evade or enable circumvention of Claude's safety guardrails, system instructions, or sandbox environments
- Infringe intellectual property rights
- Query or extract data from Claude's memory, chat history, conversation summaries, or user files

**Software must:**
- Protect user privacy and third-party privacy interests
- Collect only data necessary for its function

**Compatibility requirements (for MCP servers and skill folders):**
- Use narrow, unambiguous natural language descriptions
- Descriptions must precisely match actual functionality
- Avoid confusion or conflict with other Directory software
- Must not intentionally call or coerce Claude into calling external software
- Must not interfere with other software's tool calls
- Must not direct Claude to dynamically pull behavioral instructions from external sources
- Must contain no hidden, obfuscated, or encoded instructions

**Auto-rejection categories:**
- Financial transactions (money, cryptocurrency, financial assets)
- Generative media (images, video, audio -- except design-focused visual aids)
- Advertising (advertisements, sponsored content, paid placements)

**MCP server-specific requirements:**
- Graceful error handling
- Token-frugal design
- Tool names must not exceed 64 characters
- Remote servers must use secure OAuth 2.0
- Must provide tool annotations (readOnlyHint, destructiveHint, title)
- Support Streamable HTTP transport (SSE deprecated)

**Source**: [Anthropic Software Directory Policy](https://support.claude.com/en/articles/13145358-anthropic-software-directory-policy) - Accessed 2026-02-28
**Confidence**: High
**Verification**: [Anthropic Software Directory Terms](https://support.claude.com/en/articles/13145338-anthropic-software-directory-terms), [Discover Plugins Docs](https://code.claude.com/docs/en/discover-plugins)
**Analysis**: This is the most detailed public documentation of review criteria. The requirements are substantial -- particularly the testing account requirement, the prohibition on extracting Claude's memory/history, and the ban on dynamic external instruction loading. The auto-rejection categories for financial transactions and generative media are notable exclusions.

### Finding 5: Software Directory Terms -- Legal Obligations

**Evidence**: The Anthropic Software Directory Terms require developers to:

**Representations and warranties:**
- Maintain all necessary rights to provide the software
- Software complies with applicable laws and the Software Directory Policy
- Information provided remains accurate and up-to-date
- If collecting user data: provide privacy policies describing data collection, use, and sharing

**Rights granted to Anthropic:**
- Non-exclusive, royalty-free, worldwide license to reproduce, display, and distribute descriptions and documentation
- Right to display developer names, trademarks, logos for identifying/promoting the software
- Authorization to review, test, collect functional metadata, and share metadata with users

**Removal/termination:**
- "Anthropic has no obligation to include your Software in any Directory and may remove or refuse to display software at any time for any reason (including but not limited to violations of these terms, user complaints, security concerns, or changes to Anthropic's Software Directory Policy)"

**Indemnification:**
- Developers "agree to indemnify and hold Anthropic harmless from any claims, damages, or liabilities arising from or related to your Software or users' interactions with it"

**Source**: [Anthropic Software Directory Terms](https://support.claude.com/en/articles/13145338-anthropic-software-directory-terms) - Accessed 2026-02-28
**Confidence**: High
**Verification**: [Anthropic Software Directory Policy](https://support.claude.com/en/articles/13145358-anthropic-software-directory-policy), [Claude Plugin Submission Form](https://docs.google.com/forms/d/e/1FAIpQLSc31jdYDs_1z649BmFfX85mSSdyTXi0GOLsHD7tWKj0F_k9Dg/viewform)
**Analysis**: The terms are standard for a software marketplace. The broad removal rights ("any reason") give Anthropic complete discretion. The indemnification clause is significant -- developers assume liability for any user issues. The royalty-free license to descriptions/documentation is narrow (not a license to the plugin code itself).

### Finding 6: Repository Structure and External Plugin Examples

**Evidence**: The `anthropics/claude-plugins-official` repository contains two directories: `/plugins` (~25 Anthropic-maintained plugins) and `/external_plugins` (~13 approved third-party plugins). Currently approved external plugins include: asana, context7, firebase, github, gitlab, greptile, laravel-boost, linear, playwright, serena, slack, stripe, supabase. Direct pull requests from external contributors are automatically closed by `.github/workflows/close-external-prs.yml`, which redirects to the submission form.

The central `marketplace.json` in `.claude-plugin/` serves as the authoritative catalog. Each plugin entry requires: `name`, `description`, `category`, `source`. Optional fields include: `version`, `author`, `homepage`, `strict`, `tags`, `lspServers`.

**Source**: [claude-plugins-official GitHub Repository](https://github.com/anthropics/claude-plugins-official) - Accessed 2026-02-28
**Confidence**: High
**Verification**: [DeepWiki analysis of claude-plugins-official](https://deepwiki.com/anthropics/claude-plugins-official), [Discover Plugins Docs](https://code.claude.com/docs/en/discover-plugins), [Plugin Marketplaces Docs](https://code.claude.com/docs/en/plugin-marketplaces)
**Analysis**: The 13 approved external plugins suggest the review process is active but selective. Most approved external plugins are integrations with established services (GitHub, GitLab, Stripe, Slack, Firebase, etc.) backed by recognizable organizations. This may indicate a preference for plugins from known commercial entities in the early stages.

### Finding 7: Plugin Version Pinning and Resubmission

**Evidence**: The submission form states: "Plugins verified at specific versions; changes require resubmission. Plugin name must remain unchanged." The marketplace.json supports pinning via `sha` (exact commit) and `ref` (branch/tag) fields on plugin source entries.
**Source**: [Claude Plugin Submission Form](https://docs.google.com/forms/d/e/1FAIpQLSc31jdYDs_1z649BmFfX85mSSdyTXi0GOLsHD7tWKj0F_k9Dg/viewform) - Accessed 2026-02-28
**Confidence**: High
**Verification**: [Plugin Marketplaces Documentation](https://code.claude.com/docs/en/plugin-marketplaces), [claude-plugins-official marketplace.json](https://github.com/anthropics/claude-plugins-official/blob/main/.claude-plugin/marketplace.json)
**Analysis**: This means every plugin update requires a new submission/review cycle. The immutability of the plugin name prevents namespace squatting after approval. For nWave, this means the initial submission must use the final intended name.

### Finding 8: Alternative Distribution -- Self-Hosted Marketplace

**Evidence**: The official documentation explicitly supports self-hosted marketplaces as an alternative: "To distribute plugins independently, create your own marketplace and share it with users." A marketplace requires only a `.claude-plugin/marketplace.json` file in a git repository, and can be added by users via `/plugin marketplace add owner/repo`. The marketplace ecosystem supports GitHub, GitLab, Bitbucket, local paths, and remote URLs.
**Source**: [Create and Distribute a Plugin Marketplace](https://code.claude.com/docs/en/plugin-marketplaces) - Accessed 2026-02-28
**Confidence**: High
**Verification**: [Discover Plugins Docs](https://code.claude.com/docs/en/discover-plugins), [Claude Code Plugins Blog Post](https://claude.com/blog/claude-code-plugins)
**Analysis**: Self-hosted marketplaces are a first-class distribution mechanism. The blog post notes community members are already leading marketplace development. For nWave, a self-hosted marketplace is a viable parallel path that provides immediate distribution without waiting for Anthropic review. Many community plugins already distribute this way.

### Finding 9: Complete Plugin Manifest Schema (plugin.json)

**Evidence**: The official plugins reference documents the complete `.claude-plugin/plugin.json` schema. The manifest is optional -- if omitted, Claude Code auto-discovers components from default locations and derives the plugin name from the directory name. If included, `name` is the only required field (kebab-case, no spaces, unique across installed plugins).

Complete schema fields:
```json
{
  "name": "plugin-name",           // REQUIRED. kebab-case, unique identifier + namespace prefix
  "version": "1.2.0",              // Semantic version (MAJOR.MINOR.PATCH)
  "description": "Brief plugin description",
  "author": {
    "name": "Author Name",
    "email": "author@example.com",
    "url": "https://github.com/author"
  },
  "homepage": "https://docs.example.com/plugin",
  "repository": "https://github.com/author/plugin",
  "license": "MIT",
  "keywords": ["keyword1", "keyword2"],
  "commands": ["./custom/commands/special.md"],
  "agents": "./custom/agents/",
  "skills": "./custom/skills/",
  "hooks": "./config/hooks.json",
  "mcpServers": "./mcp-config.json",
  "outputStyles": "./styles/",
  "lspServers": "./.lsp.json"
}
```

Key rules:
- Custom component paths supplement default directories; they do not replace them
- All paths must be relative to plugin root and start with `./`
- Multiple paths can be specified as arrays
- `${CLAUDE_PLUGIN_ROOT}` environment variable resolves to absolute plugin path at runtime
- Do NOT place commands/, agents/, skills/, or hooks/ inside `.claude-plugin/` -- only plugin.json goes there

**Source**: [Plugins Reference - Claude Code Docs](https://code.claude.com/docs/en/plugins-reference) - Accessed 2026-03-03
**Confidence**: High
**Verification**: [Create Plugins - Claude Code Docs](https://code.claude.com/docs/en/plugins), [Plugin Marketplaces Docs](https://code.claude.com/docs/en/plugin-marketplaces)
**Analysis**: The manifest is lightweight by design. The only strictly required field is `name`. For marketplace submission, however, the submission form requires additional metadata (description, examples) that go beyond the manifest.

### Finding 10: Complete Marketplace.json Schema

**Evidence**: The marketplace catalog file (`.claude-plugin/marketplace.json`) has the following schema:

**Required top-level fields:**
- `name` (string): Marketplace identifier (kebab-case). Reserved names blocked: `claude-code-marketplace`, `claude-code-plugins`, `claude-plugins-official`, `anthropic-marketplace`, `anthropic-plugins`, `agent-skills`, `life-sciences`. Names impersonating official marketplaces are also blocked.
- `owner` (object): `name` (required string), `email` (optional string)
- `plugins` (array): List of plugin entries

**Optional metadata:**
- `metadata.description` (string): Brief marketplace description
- `metadata.version` (string): Marketplace version
- `metadata.pluginRoot` (string): Base directory for relative plugin source paths

**Per-plugin entry required fields:**
- `name` (string): Plugin identifier (kebab-case)
- `source` (string|object): Where to fetch the plugin. Types: relative path (`"./plugins/name"`), GitHub (`{"source": "github", "repo": "owner/repo", "ref": "v1.0", "sha": "..."}`) , git URL (`{"source": "url", "url": "https://...git", "ref": "...", "sha": "..."}`), npm (`{"source": "npm", "package": "@scope/name", "version": "^2.0.0", "registry": "..."}`), pip (`{"source": "pip", "package": "name", "version": "...", "registry": "..."}`)

**Per-plugin optional fields:**
- `description`, `version`, `author`, `homepage`, `repository`, `license`, `keywords`
- `category` (string): For organization (known values from official directory: `development`, `productivity`, `learning`, `design`, `testing`, `database`, `deployment`, `monitoring`, `security`)
- `tags` (array): For searchability (e.g., `["community-managed"]`)
- `strict` (boolean, default: true): When true, plugin.json is the authority for components; when false, marketplace entry is the entire definition
- Component overrides: `commands`, `agents`, `hooks`, `mcpServers`, `lspServers`

Example from the official directory:
```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "claude-plugins-official",
  "description": "Directory of popular Claude Code extensions...",
  "owner": {
    "name": "Anthropic",
    "email": "support@anthropic.com"
  },
  "plugins": [
    {
      "name": "typescript-lsp",
      "description": "TypeScript/JavaScript language server for enhanced code intelligence",
      "version": "1.0.0",
      "author": { "name": "Anthropic", "email": "support@anthropic.com" },
      "source": "./plugins/typescript-lsp",
      "category": "development",
      "strict": false,
      "lspServers": { ... }
    }
  ]
}
```

**Source**: [Plugin Marketplaces - Claude Code Docs](https://code.claude.com/docs/en/plugin-marketplaces) - Accessed 2026-03-03
**Confidence**: High
**Verification**: [claude-plugins-official marketplace.json](https://github.com/anthropics/claude-plugins-official/blob/main/.claude-plugin/marketplace.json), [Plugins Reference](https://code.claude.com/docs/en/plugins-reference)
**Analysis**: The marketplace.json schema is comprehensive and well-documented. The `strict` mode distinction is important: most third-party plugins should use `strict: true` (default) to keep plugin.json as the authority. The nine known categories provide a clear taxonomy for plugin classification.

### Finding 11: Plugin Directory Structure and Component Types

**Evidence**: A complete plugin supports six component types:

| Component | Default Location | Format |
|-----------|-----------------|--------|
| Manifest | `.claude-plugin/plugin.json` | JSON metadata |
| Skills | `skills/` | Directories with `SKILL.md` files |
| Commands | `commands/` | Markdown files (legacy; use skills for new) |
| Agents | `agents/` | Markdown with YAML frontmatter (name, description) |
| Hooks | `hooks/hooks.json` | JSON config with event matchers |
| MCP Servers | `.mcp.json` | Standard MCP config |
| LSP Servers | `.lsp.json` | Language server config |
| Settings | `settings.json` | Default settings (only `agent` key supported) |

Available hook events: PreToolUse, PostToolUse, PostToolUseFailure, PermissionRequest, UserPromptSubmit, Notification, Stop, SubagentStart, SubagentStop, SessionStart, SessionEnd, TeammateIdle, TaskCompleted, PreCompact.

Hook types: `command` (shell), `prompt` (LLM evaluation), `agent` (agentic verifier with tools).

Plugin caching: Marketplace plugins are copied to `~/.claude/plugins/cache`. Plugins cannot reference files outside their directory (path traversal blocked). Symlinks are followed during copy and can be used for shared dependencies.

**Source**: [Plugins Reference - Claude Code Docs](https://code.claude.com/docs/en/plugins-reference) - Accessed 2026-03-03
**Confidence**: High
**Verification**: [Create Plugins](https://code.claude.com/docs/en/plugins), [Plugin Marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)

### Finding 12: Plugin Marketplace Categories from Official Directory

**Evidence**: The official `claude-plugins-official` marketplace organizes 40+ plugins across these categories:

**Code intelligence (LSP)**: typescript-lsp, pyright-lsp, gopls-lsp, rust-analyzer-lsp, clangd-lsp, php-lsp, swift-lsp, kotlin-lsp, csharp-lsp, jdtls-lsp, lua-lsp

**External integrations (MCP)**: github, gitlab, atlassian, asana, linear, notion, figma, vercel, firebase, supabase, slack, sentry, stripe

**Development workflows**: commit-commands, pr-review-toolkit, agent-sdk-dev, plugin-dev, feature-dev, code-review, code-simplifier, skill-creator, playground, hookify, frontend-design, ralph-loop

**Output styles**: explanatory-output-style, learning-output-style

**Community/external**: qodo-skills (with SHA pinning), greptile, serena, laravel-boost, playwright, semgrep, sonatype-guide, coderabbit, posthog, context7

Some plugins carry an "Anthropic Verified" badge: Frontend Design, Code Review, Feature Dev, Code Simplifier, Ralph Loop, TypeScript LSP, among others.

**Source**: [claude-plugins-official marketplace.json](https://github.com/anthropics/claude-plugins-official/blob/main/.claude-plugin/marketplace.json) - Accessed 2026-03-03
**Confidence**: High
**Verification**: [Plugins for Claude Code and Cowork](https://claude.com/plugins), [Discover Plugins](https://code.claude.com/docs/en/discover-plugins)

## Source Analysis

| Source | Domain | Reputation | Type | Access Date | Cross-verified |
|--------|--------|------------|------|-------------|----------------|
| Discover and Install Plugins - Claude Code Docs | code.claude.com | High (1.0) | Official documentation | 2026-02-28 | Y |
| Plugin Marketplaces - Claude Code Docs | code.claude.com | High (1.0) | Official documentation | 2026-02-28 | Y |
| claude-plugins-official README | github.com/anthropics | High (1.0) | Official source repo | 2026-02-28 | Y |
| claude-plugins-official external_plugins | github.com/anthropics | High (1.0) | Official source repo | 2026-02-28 | Y |
| Plugins for Claude Code and Cowork | claude.com | High (1.0) | Official directory | 2026-02-28 | Y |
| Anthropic Software Directory Policy | support.claude.com | High (1.0) | Official policy | 2026-02-28 | Y |
| Anthropic Software Directory Terms | support.claude.com | High (1.0) | Official legal terms | 2026-02-28 | Y |
| Claude Plugin Submission Form | docs.google.com (Anthropic) | High (1.0) | Official submission form | 2026-02-28 | Y |
| Claude Code Plugins Blog Post | claude.com/blog | High (1.0) | Official announcement | 2026-02-28 | Y |
| DeepWiki analysis of claude-plugins-official | deepwiki.com | Medium (0.6) | Third-party analysis | 2026-02-28 | Y |

| Plugins Reference - Claude Code Docs | code.claude.com | High (1.0) | Official documentation | 2026-03-03 | Y |
| Create Plugins - Claude Code Docs | code.claude.com | High (1.0) | Official documentation | 2026-03-03 | Y |

Reputation: High: 11 (92%) | Medium: 1 (8%) | Avg: 0.97

## Knowledge Gaps

### Gap 1: Detailed Review Timeline and Process

**Issue**: No documentation specifies how long the review process takes, whether there is a queue, or what the typical turnaround is from submission to directory listing. No public SLAs exist.
**Attempted**: Official docs, submission form, policy documents, blog posts, web search.
**Recommendation**: Submit and track response time empirically. Consider reaching out via the primary contact email after 2 weeks if no response is received.

### Gap 2: Specific "Anthropic Verified" Badge Criteria

**Issue**: While the Software Directory Policy lists general requirements, the specific additional criteria for earning the "Anthropic Verified" badge (beyond basic automated review) are not documented.
**Attempted**: Plugin pages, directory policy, directory terms, blog posts.
**Recommendation**: The badge appears on Anthropic's own plugins and select external ones with established commercial backing. It may be an internal editorial decision rather than a checklist-based process.

### Gap 3: Difference Between the Three Submission Channels

**Issue**: It is unclear whether the Google Form at `clau.de/plugin-directory-submission`, the Claude.ai in-app form at `claude.ai/settings/plugins/submit`, and the Console form at `platform.claude.com/plugins/submit` are identical or serve different purposes. They may share a backend, or the in-app forms may be newer replacements.
**Attempted**: Documentation says all three exist. Could not access in-app forms without authentication.
**Recommendation**: Use the Google Form (linked from the official repository) as the primary channel, as it is the most explicitly documented and publicly accessible.

### Gap 4: Acceptance Rate and Selection Criteria for Non-Integration Plugins

**Issue**: All 13 approved external plugins are integrations with established commercial services. No methodology/workflow plugins (like nWave) appear in the external plugins directory yet. It is unclear whether such plugins would be evaluated differently or face different criteria.
**Attempted**: Repository analysis, directory browsing, web search.
**Recommendation**: nWave's nature as a development methodology plugin (not a service integration) may be novel in this directory. Emphasize the three use-case examples requirement and frame nWave's value clearly for the reviewer audience.

## Recommendations for nWave

### Immediate Action: Submit to the Official Directory

1. **Prepare the submission form fields:**
   - Plugin Name: `nwave` (short, matches the package name)
   - Description: 50-100 words describing nWave as an AI-powered workflow framework for disciplined TDD-based development
   - Target: Claude Code
   - GitHub Link: The public `nwave-ai/nwave` repository (not the private nWave-dev)
   - Company/Organization URL: Project homepage or GitHub organization
   - Contact Email: Primary maintainer email
   - Three Use Cases: (1) Outside-In TDD with specialized agents, (2) Architecture design through wave methodology, (3) Code review with peer review agents

2. **Ensure compliance with Software Directory Policy:**
   - Add a privacy policy (nWave does not collect user data -- state this explicitly)
   - Verify documentation covers functionality, purpose, and troubleshooting
   - Prepare a test account / sample project demonstrating core functionality
   - Review all agent definitions and skills for compliance with "no hidden instructions" and "no dynamic external instruction loading" rules
   - Ensure no tool names exceed 64 characters

3. **Be aware of version pinning**: The approved version is frozen; updates require resubmission.

### Parallel Action: Self-Hosted Marketplace

nWave already has a `.claude-plugin/marketplace.json` structure. Users can install immediately via:
```
/plugin marketplace add nwave-ai/nwave
/plugin install nwave@nwave-marketplace
```

This provides immediate distribution while the official directory submission is pending review.

### Potential Compliance Concerns for nWave

- **Dynamic instruction loading**: nWave agents load skills from files. Ensure skills are bundled within the plugin directory and not fetched from external URLs at runtime.
- **DES hooks**: The hook system modifies Claude's behavior. Ensure descriptions accurately reflect this ("enforces TDD phase discipline" not "controls Claude").
- **Agent definitions with imperative instructions**: Verify these comply with "narrow, unambiguous natural language" requirements.

## Full Citations

[1] Anthropic. "Discover and install prebuilt plugins through marketplaces". Claude Code Docs. 2026. https://code.claude.com/docs/en/discover-plugins. Accessed 2026-02-28.
[2] Anthropic. "Create and distribute a plugin marketplace". Claude Code Docs. 2026. https://code.claude.com/docs/en/plugin-marketplaces. Accessed 2026-02-28.
[3] Anthropic. "Claude Plugins Official - README". GitHub. 2026. https://github.com/anthropics/claude-plugins-official/blob/main/README.md. Accessed 2026-02-28.
[4] Anthropic. "Claude Plugins Official - External Plugins". GitHub. 2026. https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins. Accessed 2026-02-28.
[5] Anthropic. "Plugins for Claude Code and Cowork". claude.com. 2026. https://claude.com/plugins. Accessed 2026-02-28.
[6] Anthropic. "Software Directory Policy". Claude Help Center. 2026. https://support.claude.com/en/articles/13145358-anthropic-software-directory-policy. Accessed 2026-02-28.
[7] Anthropic. "Software Directory Terms". Claude Help Center. 2026. https://support.claude.com/en/articles/13145338-anthropic-software-directory-terms. Accessed 2026-02-28.
[8] Anthropic. "Claude Plugin Submission Form". Google Forms. 2026. https://docs.google.com/forms/d/e/1FAIpQLSc31jdYDs_1z649BmFfX85mSSdyTXi0GOLsHD7tWKj0F_k9Dg/viewform. Accessed 2026-02-28.
[9] Anthropic. "Customize Claude Code with plugins". Claude Blog. 2025. https://claude.com/blog/claude-code-plugins. Accessed 2026-02-28.
[10] DeepWiki. "anthropics/claude-plugins-official". deepwiki.com. 2026. https://deepwiki.com/anthropics/claude-plugins-official. Accessed 2026-02-28.
[11] Anthropic. "Plugins reference". Claude Code Docs. 2026. https://code.claude.com/docs/en/plugins-reference. Accessed 2026-03-03.
[12] Anthropic. "Create plugins". Claude Code Docs. 2026. https://code.claude.com/docs/en/plugins. Accessed 2026-03-03.

## Research Metadata

Duration: ~25 min (total, including 2026-03-03 update) | Examined: 16 | Cited: 12 | Cross-refs: 10 | Confidence: High 100% | Output: docs/research/claude-code-plugin-submission-process.md
