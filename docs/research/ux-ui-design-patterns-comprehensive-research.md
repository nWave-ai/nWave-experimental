# UX/UI Design Patterns for Software Product Owners

## Comprehensive Research Document

**Date**: 2026-02-24
**Researcher**: nw-researcher
**Purpose**: Equip an AI product owner agent with evidence-based UX/UI knowledge for guiding intuitive and pleasant interface design during requirements gathering across web, desktop, and TUI contexts.
**Confidence**: High (30+ sources from trusted domains)

---

## Table of Contents

1. [Core UX Principles](#1-core-ux-principles)
2. [Web UI Patterns](#2-web-ui-patterns)
3. [Desktop Application UI Patterns](#3-desktop-application-ui-patterns)
4. [TUI (Terminal User Interface) Patterns](#4-tui-terminal-user-interface-patterns)
5. [Emotional Design and Delight](#5-emotional-design-and-delight)
6. [UX Research Methods for Product Owners](#6-ux-research-methods-for-product-owners)
7. [Design System Thinking](#7-design-system-thinking)
8. [Checklists and Templates](#8-checklists-and-templates)
9. [Anti-Patterns](#9-anti-patterns)
10. [Sources](#10-sources)

---

## 1. Core UX Principles

### 1.1 Nielsen's 10 Usability Heuristics

Jakob Nielsen's heuristics are the most widely referenced usability evaluation framework in industry and academia. Originally published in 1994 and refined over decades, they remain the gold standard for interface evaluation.

| # | Heuristic | Core Principle | Product Owner Guidance |
|---|-----------|---------------|----------------------|
| 1 | **Visibility of System Status** | Always keep users informed about what is going on through timely feedback | Require status indicators for all async operations. Every user action must produce visible feedback within 100ms. |
| 2 | **Match Between System and Real World** | Use language, concepts, and conventions familiar to the user | Mandate user-facing copy reviews. Ban internal jargon from the UI. Use domain language from user research. |
| 3 | **User Control and Freedom** | Provide clearly marked "emergency exits" for mistaken actions | Every destructive action requires undo or confirmation. Navigation must always allow going back. |
| 4 | **Consistency and Standards** | Follow platform conventions; same words and actions should mean the same things | Require a design system. Audit for inconsistent terminology across features. |
| 5 | **Error Prevention** | Eliminate error-prone conditions or provide confirmation before commitment | Require input validation, constraints, and confirmation dialogs for irreversible actions. |
| 6 | **Recognition Rather than Recall** | Minimize memory load by making options and actions visible | Prefer dropdowns over free text where options are known. Show recent items. Provide contextual help. |
| 7 | **Flexibility and Efficiency of Use** | Provide shortcuts for expert users without burdening novices | Require keyboard shortcuts for frequent actions. Support both mouse and keyboard workflows. |
| 8 | **Aesthetic and Minimalist Design** | Show only relevant information; every extra element competes for attention | Challenge every UI element: does this serve the user's current task? Remove decorative clutter. |
| 9 | **Help Users Recognize, Diagnose, and Recover from Errors** | Use plain language, indicate the problem, and suggest a solution | Error messages must state what happened, why, and what to do next. No error codes without explanation. |
| 10 | **Help and Documentation** | Provide searchable, task-focused documentation | Require contextual help (tooltips, inline guidance). Documentation must be structured by task, not by feature. |

**Sources**: [NN/g - 10 Usability Heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/), [Interaction Design Foundation](https://www.interaction-design.org/literature/topics/ui-design-patterns), [NN/g - Design Pattern Guidelines](https://www.nngroup.com/articles/design-pattern-guidelines/)

### 1.2 Don Norman's Design Principles

From "The Design of Everyday Things" (1988, revised 2013), Norman's six principles explain why some interfaces feel intuitive while others frustrate users.

**Affordances**: The possible actions an object allows. A button affords clicking; a slider affords dragging. Digital affordances must be made visible through visual design since screens lack physical properties.

**Signifiers**: Visual or auditory indicators that communicate where and how to act. While affordances define what is possible, signifiers make that possibility discoverable. A blue underlined word signifies "clickable link." A handle on a drawer signifies "pull here."

**Mapping**: The relationship between controls and their effects. Natural mapping leverages spatial correspondence -- a volume slider that moves up to increase volume, or stove knobs arranged to match burner positions. Poor mapping forces users to memorize arbitrary relationships.

**Feedback**: Information about the result of an action. Every user action must produce perceptible feedback. Silence after an action is the most common source of user confusion. Feedback must be immediate, informative, and proportional to the importance of the action.

**Constraints**: Limitations that guide users toward correct actions. Physical constraints (a USB plug fits one way), semantic constraints (red means stop), cultural constraints (reading direction), and logical constraints (graying out unavailable options).

**Conceptual Models**: The mental image a user forms about how a system works. Good design builds accurate conceptual models through visible structure, consistent behavior, and clear cause-effect relationships. When the user's mental model matches the system model, the interface feels intuitive.

**Sources**: [UX Magazine - Norman's Principles](https://uxmag.com/articles/understanding-don-normans-principles-of-interaction), [Wikipedia - Design of Everyday Things](https://en.wikipedia.org/wiki/The_Design_of_Everyday_Things), [UX Collective - Norman's Principles](https://uxdesign.cc/general-principles-of-design-don-normans-principles-4e2d97267905)

### 1.3 Cognitive Laws

Three laws govern how humans process information and interact with interfaces.

**Fitts's Law**: The time to acquire a target is a function of the distance to and size of the target. Practical implications:
- Make primary action buttons large and close to where the cursor already is
- Place destructive actions away from constructive ones
- Infinite edges (screen borders) are easy targets -- use them for important controls
- Touch targets must be at least 44x44px (Apple HIG) or 48x48dp (Material Design)

**Hick's Law**: Decision time increases with the number and complexity of choices. Practical implications:
- Limit primary navigation to 5-7 items
- Use progressive disclosure to hide advanced options
- Break complex decisions into smaller sequential steps
- Highlight recommended options to reduce decision paralysis

**Miller's Law**: Working memory holds approximately 7 (plus or minus 2) items. Practical implications:
- Chunk information into groups of 3-5 items
- Use visual grouping (cards, sections, whitespace) to aid scanning
- Do not require users to remember information across pages
- Phone numbers, credit cards, and codes should be displayed in chunks

**Sources**: [Laws of UX](https://lawsofux.com/), [NN/g - Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/), [Interaction Design Foundation](https://www.interaction-design.org/literature/article/micro-interactions-ux)

### 1.4 Progressive Disclosure

Progressive disclosure resolves the tension between simplicity for novices and power for experts by revealing functionality in stages.

**Core rule**: Show the most important options first. Offer specialized options upon request.

**Two critical success factors**:
1. Correctly splitting features between initial and secondary views (requires user research)
2. Making the path to advanced features obvious through visible, well-labeled controls

**Design limits**: Most interfaces work best with a maximum of two disclosure levels. More than three levels causes disorientation. If that complexity is required, simplify the overall design.

**Distinguish from wizards**: Progressive disclosure uses hierarchical navigation (users return to the initial view). Staged disclosure (wizards) uses linear sequences through task steps.

**Sources**: [NN/g - Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/), [Smart Interface Design Patterns](https://smart-interface-design-patterns.com/articles/inline-validation-ux/)

### 1.5 Accessibility Essentials (WCAG)

The Web Content Accessibility Guidelines are organized around four principles (POUR):

| Principle | Meaning | Key Requirements |
|-----------|---------|-----------------|
| **Perceivable** | Information must be presentable in ways users can perceive | Text alternatives for images, captions for video, 4.5:1 contrast ratio (AA), resizable text to 200% |
| **Operable** | Interface must be navigable by all input methods | Full keyboard operation, no keyboard traps, adequate time limits, no seizure-triggering content |
| **Understandable** | Content and operation must be comprehensible | Readable text, predictable behavior, input assistance and error identification |
| **Robust** | Content must work with current and future assistive tech | Valid semantic HTML, ARIA roles where needed, compatible with screen readers |

**Product Owner minimums** (WCAG 2.2 Level AA):
- 4.5:1 contrast ratio for normal text, 3:1 for large text
- All functionality accessible via keyboard
- Focus indicators visible on all interactive elements
- Minimum target size of 24x24 CSS pixels
- Form inputs have associated labels
- Error messages identify the field and suggest correction
- Page has a descriptive title

**Sources**: [W3C - WCAG 2.2 Quick Reference](https://www.w3.org/WAI/WCAG22/quickref/), [MDN - Responsive Design](https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/CSS_layout/Responsive_Design), [BrowserStack - Responsive Breakpoints](https://www.browserstack.com/guide/responsive-design-breakpoints)

---

## 2. Web UI Patterns

### 2.1 Navigation Patterns

| Pattern | When to Use | When to Avoid |
|---------|-------------|---------------|
| **Top navigation bar** | 5-7 primary sections, marketing sites, content sites | Deep hierarchies with 20+ sections |
| **Side navigation** | Complex apps with many sections, admin dashboards | Simple sites with few pages |
| **Breadcrumbs** | Deep hierarchies, e-commerce categories | Flat site structures |
| **Command palette** (Cmd+K) | Power user tools, developer-facing apps | Consumer apps targeting non-technical users |
| **Tab bar** (mobile) | 3-5 primary destinations, mobile apps | More than 5 destinations |
| **Hamburger menu** | Secondary navigation, mobile space constraints | Primary navigation that users need frequently |
| **Mega menu** | Large sites with categorized content | Simple sites, mobile interfaces |

**Key principles**:
- Navigation should answer three questions: Where am I? Where can I go? How do I get back?
- Use consistent placement across all pages
- Highlight the current location in navigation
- Limit primary navigation to 5-7 items (Hick's Law)
- Provide search as an alternative navigation path for content-heavy applications

### 2.2 Form Design Best Practices

**Layout**:
- Place labels above input fields (highest completion rates in eye-tracking studies)
- One column layouts outperform multi-column for most forms
- Group related fields with visual proximity and clear section headings
- Place primary action buttons left-aligned with the form fields

**Validation** -- the "Reward Early, Punish Late" pattern:
- Validate on blur (when user leaves a field), not on input (while typing)
- Remove error messages immediately when the user corrects the field
- Show success indicators only when they help (e.g., password strength)
- Provide a validation summary at the top for longer forms in addition to inline errors

**Error messages must include**:
1. What went wrong (in plain language)
2. Where the error is (highlight the field)
3. How to fix it (specific guidance, not "invalid input")

**Progressive forms**:
- Split long forms across multiple steps (one-thing-per-page pattern)
- Show progress indicators for multi-step forms
- Allow saving progress and returning later
- Reduce checkout fields by 20-60% through smart defaults and progressive disclosure

**Sources**: [NN/g - Errors in Forms](https://www.nngroup.com/articles/errors-forms-design-guidelines/), [Smashing Magazine - Inline Validation](https://www.smashingmagazine.com/2022/09/inline-validation-web-forms-ux/), [Smart Interface Design Patterns - Inline Validation](https://smart-interface-design-patterns.com/articles/inline-validation-ux/)

### 2.3 Data Display Patterns

| Pattern | Best For | Key Considerations |
|---------|----------|-------------------|
| **Tables** | Structured data with multiple attributes per item, comparison tasks | Sortable columns, fixed headers, responsive collapse strategy |
| **Cards** | Browsable collections with images and summaries | Consistent card sizes, clear click targets, max 3-4 per row |
| **Lists** | Sequential items, search results, activity feeds | Clear item boundaries, scannable titles, secondary info on right |
| **Dashboards** | KPI monitoring, status overviews | Most important metrics top-left, avoid more than 7 widgets, allow customization |

**Pagination vs infinite scroll**:
- Pagination: better for goal-directed tasks (search results, admin panels) -- gives users a sense of position and control
- Infinite scroll: better for discovery-oriented browsing (social media, image galleries) -- reduces friction

### 2.4 Responsive Design Principles

**Mobile-first approach**: Design the mobile layout first, then enhance for larger screens. This ensures core content and functionality are prioritized.

**Breakpoints** (starting points, adjust to your design):
- 360-480px: Mobile
- 768px: Tablet
- 1024-1280px: Small desktop
- 1440px+: Large desktop

**Fluid typography**: Use `clamp()` for text that scales smoothly between minimum and maximum sizes without breakpoint jumps. Use `rem` and `em` over `px` for accessible text sizing.

**Container queries**: The next evolution beyond media queries -- components respond to their container's size rather than the viewport, enabling truly reusable components.

**Sources**: [MDN - Responsive Design](https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/CSS_layout/Responsive_Design), [UXPin - Responsive Design Best Practices](https://www.uxpin.com/studio/blog/best-practices-examples-of-excellent-responsive-design/), [LogRocket - CSS Breakpoints](https://blog.logrocket.com/css-breakpoints-responsive-design/)

### 2.5 Motion and Micro-interactions

**When motion helps**:
- Showing cause and effect (button press produces ripple)
- Guiding attention to changes (new item slides in)
- Providing feedback (loading spinners, progress bars)
- Explaining spatial relationships (drawer slides from side)
- Maintaining context during transitions (shared element transitions)

**When motion distracts**:
- Decorative animations with no functional purpose
- Animations that delay task completion
- Rapid or large-scale motion (accessibility: `prefers-reduced-motion`)
- Looping animations that cannot be paused

**Duration guidelines**: 100-200ms for simple state changes; 200-500ms for complex transitions; never exceed 500ms for functional animations.

### 2.6 Modern Component Patterns

| Component | Usage | Anti-pattern |
|-----------|-------|-------------|
| **Modal dialog** | Requires immediate decision; blocks until resolved | Using for information that does not require action; stacking modals |
| **Toast/snackbar** | Non-critical confirmation ("Item saved") | Critical errors or information users must not miss |
| **Drawer/sheet** | Supplementary content or filters alongside main view | Primary content or complex multi-step forms |
| **Popover/tooltip** | Contextual help or previews on hover/focus | Critical information or complex interactions |
| **Command palette** | Quick access to actions via keyboard | Only navigation method (users need visual alternatives) |

---

## 3. Desktop Application UI Patterns

### 3.1 Native vs Cross-Platform Considerations

**Native advantages**: Platform conventions feel familiar; better system integration (file dialogs, notifications, drag-and-drop); consistent with OS look and feel; better accessibility through native APIs.

**Cross-platform tradeoffs**: Shared codebase reduces development cost; visual consistency across platforms may conflict with platform expectations; custom rendering may miss OS accessibility features.

**Guidance for product owners**: If the target audience uses primarily one platform, prioritize native conventions. If cross-platform is required, follow each platform's conventions for core interactions (menus, shortcuts, window management) while sharing the application's domain-specific UI.

### 3.2 Core Desktop UI Elements

**Menu bar**: The primary access point for all application commands. Organize by convention: File, Edit, View, then domain-specific menus, ending with Window and Help. Every menu item should have a keyboard shortcut for frequently used actions.

**Toolbar**: Provides quick access to the most common commands. Toolbars should be configurable -- users should be able to show, hide, and rearrange toolbar items. Every toolbar button must have a tooltip.

**Status bar**: Displays contextual information about the current state (document length, cursor position, connection status, mode indicators). Keep it low-profile; it supports the user's awareness without demanding attention.

**Context menus**: Right-click menus should contain a small number of actions relevant to the selected element. Include the most common actions (Cut, Copy, Paste where applicable) and domain-specific actions for the selection context.

### 3.3 Document-Centric vs Task-Centric Layouts

**Document-centric** (Word, Photoshop, VS Code): A central canvas with surrounding tool panels. Users work on one primary artifact. Design the layout to maximize canvas space; make tool panels collapsible and dockable.

**Task-centric** (Slack, email clients, CRM tools): Multiple panels showing different aspects of a workflow. Users switch between views frequently. Design for quick navigation between task contexts; support split views and list-detail patterns.

### 3.4 Keyboard, Drag-and-Drop, Undo/Redo

**Keyboard shortcuts**:
- Follow platform conventions (Ctrl+C/Cmd+C for copy, etc.)
- Display shortcuts in menus and tooltips so users can learn them
- Provide a keyboard shortcut reference (often Ctrl+/ or ?)
- All functionality accessible via keyboard is an accessibility requirement

**Drag-and-drop**:
- Always provide an alternative non-drag method (cut/paste, move dialog)
- Show clear drop targets with visual highlighting
- Provide cursor feedback (copy vs move indicators)
- Support undo for accidental drops

**Undo/redo**:
- Support multi-level undo (at minimum 20 levels)
- Make the undo stack visible when possible (edit history panel)
- Distinguish between undoable actions and permanent ones (clearly warn for permanent actions)

### 3.5 Multi-Window and Panel Management

- Allow users to resize, collapse, dock, and undock panels
- Persist layout preferences across sessions
- Provide a "Reset Layout" option for when users get lost
- Support splitting the view (side-by-side editing, comparison views)
- Minimize mode switches -- keep related information visible simultaneously when possible

### 3.6 Settings and Preferences

- Organize settings by category with a left sidebar navigation
- Show the current value of each setting (do not make users click to discover it)
- Provide search within settings for applications with many options
- Use sensible defaults so most users never need to change settings
- Distinguish between application-level and document-level settings

**Sources**: [Microsoft Learn - Desktop UX](https://learn.microsoft.com/en-us/windows/win32/uxguide/how-to-design-desktop-ux), [Microsoft Learn - Toolbars](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/bb226788(v=vs.85)), [Microsoft Learn - Keyboard UI Design](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/dnacc/guidelines-for-keyboard-user-interface-design), [ToDesktop - Cross-Platform UX](https://www.todesktop.com/blog/posts/designing-desktop-apps-cross-platform-ux)

---

## 4. TUI (Terminal User Interface) Patterns

### 4.1 CLI Argument Design

**Command structure**: Follow the `program subcommand [flags] [arguments]` pattern (e.g., `git commit -m "message"`).

**Flags and options**:
- Provide both short (`-h`) and long (`--help`) versions of common flags
- Reserve single-letter flags for frequently used options
- Standard flags to always support: `--help`, `--version`, `--verbose`/`--quiet`, `--no-color`
- Never accept secrets via flags (use files, stdin, or environment variables)
- Make flag order independent

**Subcommands**:
- Use verbs for actions: `create`, `delete`, `list`, `show`, `update`
- Use nouns for resource targets: `user`, `project`, `config`
- Pattern: `tool resource action` or `tool action resource` -- pick one and be consistent
- Provide shell completion scripts for discoverability

### 4.2 Interactive TUI Frameworks

| Framework | Language | Architecture | Best For |
|-----------|----------|-------------|----------|
| **Bubble Tea** | Go | Elm Architecture (Model-Update-View) | Full TUI applications with complex state |
| **Rich** | Python | Declarative rendering | Beautiful output, progress bars, tables, trees |
| **Ink** | JavaScript | React component model | TUIs built by teams with React experience |
| **Textual** | Python | CSS-like styling, widget system | Python dashboard-style applications |
| **Ratatui** | Rust | Immediate-mode rendering | High-performance terminal applications |

**Key architectural pattern** (from Bubble Tea/Elm Architecture):
- **Model**: The application state (a single data structure)
- **Update**: A pure function that takes the current model and a message, returns a new model
- **View**: A pure function that renders the model to a string

This unidirectional data flow makes TUI state management predictable and testable.

### 4.3 Color and Formatting for Readability

**Color conventions**:
- Red: errors, failures, deletions
- Yellow/amber: warnings, things that need attention
- Green: success, confirmations, additions
- Blue/cyan: information, links, highlights
- Dim/gray: secondary information, metadata

**Rules for color use**:
- Never use color as the only way to convey information (accessibility)
- Respect `NO_COLOR` environment variable (https://no-color.org/)
- Detect TTY -- disable color when output is piped or redirected
- Test with common color-blindness simulators (protanopia, deuteranopia)

**Formatting patterns**:
- Bold for emphasis and headings
- Tables for structured data (aligned columns)
- Indentation for hierarchy
- Horizontal rules for section breaks
- Unicode box-drawing characters for visual structure (but provide ASCII fallback)

### 4.4 Output Design: Human-Readable vs Machine-Parseable

**Default to human-readable output**:
- Detect TTY: if stdout is a terminal, output for humans; if piped, consider simpler format
- Use colors, tables, progress bars in TTY mode
- Disable animations and spinners in non-TTY mode

**Provide machine-parseable alternatives**:
- `--json` flag for structured output (the most important machine format)
- `--plain` or `--tsv` for tabular data compatible with `grep`, `awk`, `cut`
- `--quiet` for scripts that only need the exit code

**Versioning output format**: Once you publish a `--json` schema, treat it as a contract. Breaking changes to JSON output require a major version bump or a `--output-version` flag.

### 4.5 Error Message Design for CLI

Every CLI error message should answer three questions:

1. **What happened?** -- A clear, jargon-free description of the problem
2. **Why?** -- The cause or context that led to the error
3. **What to do?** -- A concrete next step the user can take

**Example of a good CLI error message**:
```
Error: Could not connect to database at localhost:5432

  The connection was refused. This usually means the database
  server is not running or is not accepting connections on this port.

  Try:
    1. Check if PostgreSQL is running:  pg_isready -h localhost -p 5432
    2. Start the server:                sudo systemctl start postgresql
    3. Verify the port in config:       cat ~/.config/myapp/database.yaml

  Documentation: https://docs.myapp.com/troubleshooting/database
```

**Example of a bad CLI error message**:
```
Error: ECONNREFUSED
```

**Additional error guidelines**:
- Never blame the user ("You entered an invalid..." becomes "The value ... is not valid because...")
- Suggest the most likely correction (did-you-mean for typos in commands)
- Use exit codes consistently (0=success, 1=general error, 2=usage error)
- Log verbose diagnostics to a file, not to stderr by default

### 4.6 Help Text and Documentation

**`--help` output structure**:
```
tool-name - One-line description of what this tool does

USAGE
  tool-name <command> [flags]

COMMANDS
  create    Create a new resource
  list      List existing resources
  delete    Remove a resource

FLAGS
  -h, --help       Show this help message
  -v, --version    Show version information
  -q, --quiet      Suppress non-error output

EXAMPLES
  # Create a new project
  tool-name create my-project --template=web

  # List all projects
  tool-name list --format=table

LEARN MORE
  Documentation:  https://docs.tool-name.com
  Report issues:  https://github.com/org/tool-name/issues
```

**Key help text principles**:
- Lead with examples (users scan for examples first)
- Show the most common commands and flags first
- Keep descriptions to one line per command/flag
- Link to detailed documentation rather than cramming everything into help text
- Support `tool help <command>` in addition to `tool <command> --help`

### 4.7 Progress and Responsiveness

- Respond within 100ms -- output something immediately, especially before network calls
- Show a spinner for operations taking 1-5 seconds
- Show a progress bar with percentage for operations taking more than 5 seconds
- For multi-step operations, show step count: `[3/7] Installing dependencies...`
- Make operations idempotent where possible (safe to re-run after interruption)

**Sources**: [Command Line Interface Guidelines (clig.dev)](https://clig.dev/), [Lucas Costa - UX Patterns for CLI Tools](https://lucasfcosta.com/2022/06/01/ux-patterns-cli-tools.html), [Atlassian - 10 Design Principles for Delightful CLIs](https://www.atlassian.com/blog/it-teams/10-design-principles-for-delightful-clis), [Thoughtworks - CLI Design Guidelines](https://www.thoughtworks.com/en-in/insights/blog/engineering-effectiveness/elevate-developer-experiences-cli-design-guidelines), [GitHub - awesome-tuis](https://github.com/rothgar/awesome-tuis)

---

## 5. Emotional Design and Delight

### 5.1 Aarron Walter's Hierarchy of User Needs

Adapted from Maslow's hierarchy, Walter's model defines four layers that must be satisfied in order:

```
        /\
       /  \
      / PL \     4. PLEASURABLE - Delights, surprises, emotional connection
     /------\
    / USABLE \    3. USABLE - Easy to learn, intuitive, efficient
   /----------\
  / RELIABLE   \   2. RELIABLE - Consistent, dependable, no crashes
 /--------------\
/ FUNCTIONAL     \  1. FUNCTIONAL - It works, it serves its purpose
------------------
```

**Critical insight for product owners**: A product can be delightful only if it is usable. Never invest in delight features before the foundation is solid. Beautiful animations on a buggy, confusing interface make things worse, not better.

### 5.2 Surface Delight vs Deep Delight

**Surface delight** (momentary, contextual):
- Playful animations on button hover
- Witty microcopy in error messages
- Surprising easter eggs
- Visually pleasing illustrations

**Deep delight** (sustained, holistic):
- The interface anticipates what the user needs next
- Complex tasks feel effortless
- Users achieve "flow" state -- immersed productivity without obstruction
- The tool becomes an extension of the user's thinking

**Prioritization rule**: Deep delight generates loyalty and return usage. Surface delight creates momentary positive reactions but cannot compensate for usability failures. Invest in deep delight first.

### 5.3 Empty States

Empty states (no data, first use, error result) are opportunities, not dead ends.

**Good empty state design**:
- Explain what will appear here when there is content
- Provide a clear call to action to create the first item
- Use illustration or visual interest to make the state feel intentional
- Offer guidance or templates for first-time users

**Anti-pattern**: A blank page with no guidance, or a generic "No results found" with no suggested next step.

### 5.4 Onboarding and First-Run Experience

**Progressive onboarding** (preferred over feature tours):
- Let users start doing real work immediately
- Introduce features in context, at the moment they become relevant
- Use tooltips and inline hints that dismiss after first use
- Offer a "skip" option for experienced users

**Anti-pattern**: A mandatory 8-step walkthrough that blocks the user from doing anything before completing it.

### 5.5 Tone of Voice in UI Copy

**Principles for UI writing**:
- Be clear first, clever second
- Use active voice and present tense
- Address the user as "you"
- Keep instructions to 1-2 sentences
- Match tone to emotional context: error messages are empathetic, success messages are encouraging, neutral actions are straightforward
- A consistent voice builds trust; an inconsistent voice creates unease

**Sources**: [NN/g - Theory of User Delight](https://www.nngroup.com/articles/theory-user-delight/), [NN/g - Three Pillars of User Delight](https://www.nngroup.com/articles/pillars-user-delight/), [Aarron Walter - Designing for Emotion](https://www.aarronwalter.com/book), [LogRocket - Empty State UX](https://blog.logrocket.com/ux-design/empty-state-ux/), [Interaction Design Foundation - Micro-interactions](https://www.interaction-design.org/literature/article/micro-interactions-ux)

---

## 6. UX Research Methods for Product Owners

### 6.1 Lightweight Usability Testing

| Method | Time Required | Participants | When to Use |
|--------|-------------|-------------|-------------|
| **5-second test** | 5 min per participant | 5-10 | Test first impressions: show a screen for 5 seconds, ask what they remember |
| **First-click test** | 10 min per participant | 5-10 | Validate navigation: give a task, record where users click first |
| **Think-aloud protocol** | 30-60 min per participant | 5 | Deep usability evaluation: users narrate their thought process |
| **Hallway testing** | 5-10 min | 3-5 | Quick sanity check: grab colleagues unfamiliar with the feature |
| **Unmoderated remote test** | Self-paced | 10-20 | Scale testing: tools like Maze, UserTesting record sessions asynchronously |

**The "magic number 5" rule** (Nielsen): Testing with 5 users uncovers approximately 85% of usability problems. Iterate testing across rounds rather than testing many users once.

### 6.2 A/B Testing Fundamentals

- Test one variable at a time (button color, copy, layout -- not all at once)
- Define a success metric before starting (conversion rate, task completion time, error rate)
- Run tests long enough to reach statistical significance (minimum 1-2 weeks for most web apps)
- Be wary of local maxima -- A/B tests optimize existing designs, not discover fundamentally better approaches
- Combine quantitative A/B results with qualitative usability testing for full understanding

### 6.3 Journey Mapping

A journey map visualizes the complete experience a user has achieving a goal, including:
- **Stages**: The major phases of the journey (awareness, consideration, action, retention)
- **Actions**: What the user does at each stage
- **Thoughts**: What the user is thinking
- **Emotions**: The user's emotional state (frustration, confidence, delight)
- **Pain points**: Where the experience breaks down
- **Opportunities**: Where improvements would have the greatest impact

**Product owner use**: Create journey maps during DISCUSS phase to identify the full context of user stories. A single user story may span multiple journey stages.

### 6.4 Card Sorting for Information Architecture

**Open card sort**: Give users content items on cards; they create their own categories. Use when you have no existing structure.

**Closed card sort**: Give users content items and predefined categories; they sort items into categories. Use when validating an existing navigation structure.

**Hybrid card sort**: Provide some predefined categories but allow users to create new ones. Best balance of structure and discovery.

**Minimum participants**: 15-20 for quantitative analysis; 5-7 for qualitative insights.

### 6.5 Heuristic Evaluation Checklist

A structured review against Nielsen's 10 heuristics. For each screen or workflow:

1. Is system status visible? (loading, saving, errors, success)
2. Does the language match the user's vocabulary?
3. Can users undo or escape from any state?
4. Are similar things named and behaving consistently?
5. Are error-prone situations prevented or confirmed?
6. Are options visible rather than requiring recall?
7. Are there shortcuts for frequent actions?
8. Is every visible element necessary for the current task?
9. Do error messages explain the problem and solution?
10. Is contextual help available?

Score each on a severity scale (0=not a problem, 4=usability catastrophe). Prioritize fixing 3s and 4s before launch.

**Sources**: [NN/g - Which UX Research Methods](https://www.nngroup.com/articles/which-ux-research-methods/), [Maze - UX Research Methods](https://maze.co/guides/ux-research/methods/), [Optimal Workshop - Heuristic Evaluation](https://www.optimalworkshop.com/blog/usability-experts-unite-the-power-of-heuristic-evaluation-in-user-interface-design), [Contentsquare - 13 UX Research Methods](https://contentsquare.com/guides/ux-research/methods/)

---

## 7. Design System Thinking

### 7.1 Component-Driven Design

A design system is a collection of reusable components and clear standards that teams use to build consistent interfaces at scale. It is not a UI kit -- it includes principles, patterns, documentation, and governance.

**Component hierarchy**:
- **Atoms**: Buttons, inputs, labels, icons
- **Molecules**: Search bar (input + button), form field (label + input + error message)
- **Organisms**: Header (logo + nav + search), card grid, form section
- **Templates**: Page-level layouts composing organisms
- **Pages**: Specific instances of templates with real content

### 7.2 Design Tokens

Design tokens are the atomic values that define visual design: colors, spacing, typography, shadows, borders, motion durations.

**Token hierarchy**:

| Level | Example | Purpose |
|-------|---------|---------|
| **Global/primitive** | `color-blue-500: #3B82F6` | Raw values from the design palette |
| **Alias/semantic** | `color-primary: {color-blue-500}` | Meaningful names mapping to primitives |
| **Component** | `button-background: {color-primary}` | Component-specific token references |

**Spacing scale** (8px grid is the most common):
```
spacing-1:  4px   (0.25rem)
spacing-2:  8px   (0.5rem)
spacing-3:  12px  (0.75rem)
spacing-4:  16px  (1rem)
spacing-5:  20px  (1.25rem)
spacing-6:  24px  (1.5rem)
spacing-8:  32px  (2rem)
spacing-10: 40px  (2.5rem)
spacing-12: 48px  (3rem)
spacing-16: 64px  (4rem)
```

**Typography scale** (based on a modular scale, typically 1.25 or 1.333 ratio):
```
text-xs:    12px / 16px line-height
text-sm:    14px / 20px
text-base:  16px / 24px
text-lg:    18px / 28px
text-xl:    20px / 28px
text-2xl:   24px / 32px
text-3xl:   30px / 36px
text-4xl:   36px / 40px
```

### 7.3 Consistency Principles

- **Internal consistency**: Same patterns within the same application (all modals work the same way, all forms validate the same way)
- **External consistency**: Following platform and industry conventions (Ctrl+S saves, red means error)
- **Temporal consistency**: The application behaves the same way today as it did yesterday (no surprising changes between versions)

### 7.4 When to Use Existing Design Systems vs Custom

| Situation | Recommendation |
|-----------|---------------|
| Internal tools, admin dashboards | Use an existing system (Material UI, Ant Design, Radix) |
| Consumer product with strong brand | Build a custom system on top of a headless library (Radix, Headless UI) |
| MVP or prototype | Use an existing system; customize later if needed |
| Platform with strict brand guidelines | Custom system, but adopt token and component architecture from established systems |

**Established design systems to evaluate**: Material Design (Google), Fluent Design (Microsoft), Carbon Design (IBM), Polaris (Shopify), Primer (GitHub), Lightning (Salesforce).

**Sources**: [Design.dev - Design Systems Guide](https://design.dev/guides/design-systems/), [USWDS - Design Tokens](https://designsystem.digital.gov/design-tokens/), [UXPin - What Are Design Tokens](https://www.uxpin.com/studio/blog/what-are-design-tokens/), [Penpot - Design Tokens Guide](https://penpot.app/blog/what-are-design-tokens-a-complete-guide/), [Telerik - Design Tokens Building Blocks](https://www.telerik.com/blogs/design-tokens-fundamental-building-blocks-design-systems)

---

## 8. Checklists and Templates

### 8.1 Product Owner UX Review Checklist

Use this checklist when reviewing designs or writing acceptance criteria:

```markdown
## UX Review Checklist

### Visibility and Feedback
- [ ] Every user action produces visible feedback within 100ms
- [ ] Loading states are shown for operations taking >1 second
- [ ] Success confirmations are shown for state-changing actions
- [ ] Error states are clearly communicated with recovery guidance

### Navigation and Orientation
- [ ] User can always answer: Where am I? Where can I go? How do I get back?
- [ ] Breadcrumbs or other wayfinding for deep hierarchies
- [ ] Primary navigation has 7 or fewer items

### Forms and Input
- [ ] Labels are above fields
- [ ] Validation uses "reward early, punish late" pattern
- [ ] Error messages state what, where, and how to fix
- [ ] Required fields are clearly marked
- [ ] Destructive actions require confirmation

### Accessibility (WCAG 2.2 AA)
- [ ] Color contrast ratio >= 4.5:1 for text
- [ ] All functionality accessible via keyboard
- [ ] Focus indicators are visible
- [ ] Touch/click targets >= 24x24px
- [ ] Images have alt text
- [ ] Form fields have associated labels

### Cognitive Load
- [ ] Choices per decision point <= 7
- [ ] Information is chunked into scannable groups
- [ ] Progressive disclosure hides advanced options
- [ ] No requirement to remember info across pages

### Consistency
- [ ] Same action looks and behaves the same everywhere
- [ ] Terminology is consistent throughout
- [ ] Platform conventions are followed
- [ ] Design tokens from the system are used (no magic numbers)

### Delight (only after above are satisfied)
- [ ] Empty states are helpful, not blank
- [ ] Onboarding is progressive, not a blocking tour
- [ ] Tone of voice is consistent and appropriate
- [ ] Animations respect prefers-reduced-motion
```

### 8.2 CLI/TUI UX Review Checklist

```markdown
## CLI/TUI UX Review Checklist

### Discoverability
- [ ] --help produces useful, example-led output
- [ ] Subcommands use consistent verb/noun patterns
- [ ] Shell completion scripts are available
- [ ] Did-you-mean suggestions for typos

### Output
- [ ] Default output is human-readable with color in TTY
- [ ] --json flag available for machine consumption
- [ ] Color is never the only way to convey information
- [ ] NO_COLOR environment variable is respected
- [ ] Animations disabled in non-TTY mode

### Error Handling
- [ ] Error messages answer: what happened, why, what to do
- [ ] No raw stack traces in user-facing output
- [ ] Exit codes are consistent (0=success, 1=error, 2=usage)
- [ ] Suggestions for common mistakes

### Responsiveness
- [ ] First output appears within 100ms
- [ ] Spinner for 1-5 second operations
- [ ] Progress bar with percentage for longer operations
- [ ] Ctrl+C handled cleanly with proper cleanup

### Configuration
- [ ] Flags > env vars > project config > user config > defaults
- [ ] Secrets never accepted via flags
- [ ] Sensible defaults for all optional configuration
```

### 8.3 Acceptance Criteria Template with UX Requirements

```gherkin
Feature: [Feature Name]

  # UX Context
  # Platform: [web | desktop | TUI]
  # Key heuristics: [list applicable Nielsen heuristics]
  # Accessibility: WCAG 2.2 AA required

  Scenario: Happy path
    Given [context]
    When [user action]
    Then [expected visible result]
    And system provides feedback within 100ms
    And the action can be undone via [mechanism]

  Scenario: Error state
    Given [context leading to error]
    When [user action that triggers error]
    Then an error message explains what happened
    And the error message explains why it happened
    And the error message suggests what to do next
    And the error is shown inline next to the relevant field

  Scenario: Empty state
    Given no [resources] exist yet
    When the user navigates to the [resource] view
    Then a helpful message explains what [resources] are
    And a clear call to action is provided to create the first one

  Scenario: Keyboard accessibility
    Given the user navigates with keyboard only
    When they tab through the interface
    Then all interactive elements are reachable
    And focus indicators are visible
    And Enter/Space activate focused elements
```

---

## 9. Anti-Patterns

### 9.1 Universal Anti-Patterns

| Anti-Pattern | Why It Fails | Alternative |
|-------------|-------------|-------------|
| **Mystery meat navigation** | Icons without labels force users to guess | Label all navigation items; use icons as supplements, not replacements |
| **Infinite nested modals** | Stacking dialogs disorients users | Use inline expansion or navigate to a new page |
| **Confirm-shaming** | Manipulative copy damages trust ("No, I don't want to save money") | Neutral, respectful option labels |
| **Dark patterns** | Designed to trick users into unintended actions | Transparent, honest UI that respects user intent |
| **Feature-itis** | Adding features without removing complexity | Apply progressive disclosure; audit feature usage; sunset unused features |
| **Jargon in the UI** | Internal terms confuse external users | Use language from user research and domain vocabulary |
| **Invisible system status** | No feedback after actions causes anxiety | Every action produces visible feedback |

### 9.2 Web-Specific Anti-Patterns

| Anti-Pattern | Alternative |
|-------------|-------------|
| Autoplay video with sound | Mute by default, user-initiated play |
| Full-page interstitials on mobile | Inline or bottom-sheet prompts |
| Captchas for every action | Risk-based authentication, invisible captchas |
| Horizontal scrolling for content | Responsive layout that fits viewport |
| Form validation only on submit (no inline) | Inline validation with "reward early, punish late" |

### 9.3 Desktop-Specific Anti-Patterns

| Anti-Pattern | Alternative |
|-------------|-------------|
| No keyboard shortcuts | Full keyboard support with discoverable shortcuts |
| Single-level undo | Multi-level undo with visible history |
| Modal settings that reset on cancel | Apply/Cancel with intermediate preview |
| Ignoring OS conventions (non-native file dialogs) | Use platform-native dialogs for file operations |

### 9.4 CLI/TUI-Specific Anti-Patterns

| Anti-Pattern | Alternative |
|-------------|-------------|
| Wall of unformatted text output | Structured output with headers, tables, color |
| Raw exception stack traces as errors | Caught errors rewritten in human language |
| No --help or misleading help | Comprehensive, example-led help text |
| Requiring interactive input in CI/CD contexts | Detect non-TTY and accept flags/env vars instead |
| Breaking JSON output format between versions | Treat machine output as a versioned API contract |

---

## 10. Sources

### High-Reputation Sources (Academic/Official/Industry Leaders)

1. Nielsen Norman Group - [10 Usability Heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/) - Accessed 2026-02-24
2. Nielsen Norman Group - [Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/) - Accessed 2026-02-24
3. Nielsen Norman Group - [Theory of User Delight](https://www.nngroup.com/articles/theory-user-delight/) - Accessed 2026-02-24
4. Nielsen Norman Group - [Three Pillars of User Delight](https://www.nngroup.com/articles/pillars-user-delight/) - Accessed 2026-02-24
5. Nielsen Norman Group - [Errors in Forms Design Guidelines](https://www.nngroup.com/articles/errors-forms-design-guidelines/) - Accessed 2026-02-24
6. Nielsen Norman Group - [Which UX Research Methods](https://www.nngroup.com/articles/which-ux-research-methods/) - Accessed 2026-02-24
7. Nielsen Norman Group - [Design Pattern Guidelines](https://www.nngroup.com/articles/design-pattern-guidelines/) - Accessed 2026-02-24
8. W3C - [WCAG 2.2 Quick Reference](https://www.w3.org/WAI/WCAG22/quickref/) - Accessed 2026-02-24
9. MDN Web Docs - [Responsive Design](https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/CSS_layout/Responsive_Design) - Accessed 2026-02-24
10. Microsoft Learn - [Desktop UX Design](https://learn.microsoft.com/en-us/windows/win32/uxguide/how-to-design-desktop-ux) - Accessed 2026-02-24
11. Microsoft Learn - [Keyboard UI Design Guidelines](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/dnacc/guidelines-for-keyboard-user-interface-design) - Accessed 2026-02-24
12. Microsoft Learn - [Toolbar Design Guidelines](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/bb226788(v=vs.85)) - Accessed 2026-02-24
13. Microsoft Learn - [Windows App Design](https://learn.microsoft.com/en-us/windows/apps/design/) - Accessed 2026-02-24
14. Command Line Interface Guidelines - [clig.dev](https://clig.dev/) - Accessed 2026-02-24
15. Laws of UX - [lawsofux.com](https://lawsofux.com/) - Accessed 2026-02-24
16. Interaction Design Foundation - [Micro-interactions UX](https://www.interaction-design.org/literature/article/micro-interactions-ux) - Accessed 2026-02-24
17. Interaction Design Foundation - [UI Design Patterns](https://www.interaction-design.org/literature/topics/ui-design-patterns) - Accessed 2026-02-24
18. Thoughtworks - [CLI Design Guidelines](https://www.thoughtworks.com/en-in/insights/blog/engineering-effectiveness/elevate-developer-experiences-cli-design-guidelines) - Accessed 2026-02-24
19. Smashing Magazine - [Inline Validation Web Forms](https://www.smashingmagazine.com/2022/09/inline-validation-web-forms-ux/) - Accessed 2026-02-24
20. Smart Interface Design Patterns - [Inline Validation UX](https://smart-interface-design-patterns.com/articles/inline-validation-ux/) - Accessed 2026-02-24

### Medium-High Reputation Sources

21. UX Magazine - [Norman's Principles of Interaction](https://uxmag.com/articles/understanding-don-normans-principles-of-interaction) - Accessed 2026-02-24
22. UX Collective - [Don Norman's Design Principles](https://uxdesign.cc/general-principles-of-design-don-normans-principles-4e2d97267905) - Accessed 2026-02-24
23. Lucas Costa - [UX Patterns for CLI Tools](https://lucasfcosta.com/2022/06/01/ux-patterns-cli-tools.html) - Accessed 2026-02-24
24. Atlassian - [10 Design Principles for Delightful CLIs](https://www.atlassian.com/blog/it-teams/10-design-principles-for-delightful-clis) - Accessed 2026-02-24
25. Aarron Walter - [Designing for Emotion](https://www.aarronwalter.com/book) - Accessed 2026-02-24
26. LogRocket - [Empty State UX](https://blog.logrocket.com/ux-design/empty-state-ux/) - Accessed 2026-02-24
27. LogRocket - [CSS Breakpoints](https://blog.logrocket.com/css-breakpoints-responsive-design/) - Accessed 2026-02-24
28. UXPin - [Responsive Design Best Practices](https://www.uxpin.com/studio/blog/best-practices-examples-of-excellent-responsive-design/) - Accessed 2026-02-24
29. UXPin - [What Are Design Tokens](https://www.uxpin.com/studio/blog/what-are-design-tokens/) - Accessed 2026-02-24
30. BrowserStack - [Responsive Design Breakpoints](https://www.browserstack.com/guide/responsive-design-breakpoints) - Accessed 2026-02-24
31. Design.dev - [Design Systems Guide](https://design.dev/guides/design-systems/) - Accessed 2026-02-24
32. USWDS - [Design Tokens](https://designsystem.digital.gov/design-tokens/) - Accessed 2026-02-24
33. Penpot - [Design Tokens Guide](https://penpot.app/blog/what-are-design-tokens-a-complete-guide/) - Accessed 2026-02-24
34. Telerik - [Design Tokens Building Blocks](https://www.telerik.com/blogs/design-tokens-fundamental-building-blocks-design-systems) - Accessed 2026-02-24
35. GitHub - [awesome-tuis](https://github.com/rothgar/awesome-tuis) - Accessed 2026-02-24
36. ToDesktop - [Cross-Platform UX](https://www.todesktop.com/blog/posts/designing-desktop-apps-cross-platform-ux) - Accessed 2026-02-24
37. Maze - [UX Research Methods](https://maze.co/guides/ux-research/methods/) - Accessed 2026-02-24
38. Contentsquare - [13 UX Research Methods](https://contentsquare.com/guides/ux-research/methods/) - Accessed 2026-02-24
39. Optimal Workshop - [Heuristic Evaluation](https://www.optimalworkshop.com/blog/usability-experts-unite-the-power-of-heuristic-evaluation-in-user-interface-design) - Accessed 2026-02-24
40. Wikipedia - [The Design of Everyday Things](https://en.wikipedia.org/wiki/The_Design_of_Everyday_Things) - Accessed 2026-02-24

### Foundational Books Referenced

- Norman, D. (2013). *The Design of Everyday Things: Revised and Expanded Edition*. Basic Books.
- Walter, A. (2011). *Designing for Emotion*. A Book Apart.
- Nielsen, J. (1994). *Usability Engineering*. Morgan Kaufmann.
- Krug, S. (2014). *Don't Make Me Think, Revisited*. New Riders.
- Saffer, D. (2013). *Microinteractions: Designing with Details*. O'Reilly Media.

---

## Knowledge Gaps

The following areas were searched but produced insufficient evidence for high-confidence findings:

1. **Apple HIG desktop patterns**: Apple's Human Interface Guidelines page requires JavaScript rendering and could not be fetched. The macOS-specific guidelines for menu bars, window management, and native controls were referenced from general desktop UX literature instead of the primary source. Confidence: Medium.

2. **Quantitative data on TUI usability**: While design patterns for TUIs are well-documented in practitioner blogs and framework documentation, peer-reviewed academic research specifically on terminal UI usability is sparse. Most evidence comes from practitioner experience and framework authors. Confidence: Medium.

3. **Cross-platform longitudinal studies**: No studies were found comparing user satisfaction across web, desktop, and TUI implementations of the same functionality over time. The guidance in this document is synthesized from platform-specific research rather than comparative studies.

4. **Design token standardization**: The W3C Design Tokens Community Group is working on a specification, but as of this research date, no formal standard has been ratified. Token formats vary across tools and organizations.
