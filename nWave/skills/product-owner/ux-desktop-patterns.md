---
name: ux-desktop-patterns
description: Desktop application UI patterns for product owners. Load when designing native or cross-platform desktop applications, writing desktop-specific acceptance criteria, or evaluating panel layouts and keyboard workflows.
---

# Desktop Application UI Patterns

Actionable desktop interface patterns for requirements gathering and design review. Use these when the target platform is a native or cross-platform desktop application.

## Native vs Cross-Platform

**Native advantages**: Platform conventions feel familiar; better system integration (file dialogs, notifications, drag-and-drop); consistent OS look and feel; better accessibility through native APIs.

**Cross-platform tradeoffs**: Shared codebase reduces cost; visual consistency across platforms may conflict with platform expectations; custom rendering may miss OS accessibility features.

**Guidance**: If users are primarily on one platform, prioritize native conventions. If cross-platform is required, follow each platform's conventions for core interactions (menus, shortcuts, window management) while sharing domain-specific UI.

## Core Desktop UI Elements

### Menu Bar
- Primary access point for all application commands
- Organize by convention: File, Edit, View, then domain-specific menus, ending with Window and Help
- Every menu item should have a keyboard shortcut for frequent actions
- Group related items with separators; use submenus sparingly (one level deep preferred)

### Toolbar
- Quick access to the most common commands (subset of menu bar)
- Should be configurable: users show, hide, and rearrange items
- Every toolbar button must have a tooltip
- Include both icon and text label for primary actions (icon-only for space-constrained toolbars)

### Status Bar
- Displays contextual information: document stats, cursor position, connection status, mode indicators
- Keep it low-profile: supports awareness without demanding attention
- Update in real-time to reflect current state

### Context Menus
- Right-click menus with a small number of actions relevant to the selection
- Include standard actions (Cut, Copy, Paste where applicable) plus domain-specific actions
- Mirror keyboard shortcuts shown in the main menu

## Document-Centric vs Task-Centric Layouts

### Document-Centric (Word, Photoshop, VS Code)
- Central canvas with surrounding tool panels
- Users work on one primary artifact
- Maximize canvas space; make tool panels collapsible and dockable
- Support zoom, scroll, and viewport controls
- Auto-save with visible save state indicator

### Task-Centric (Slack, email clients, CRM)
- Multiple panels showing different workflow aspects
- Users switch between views frequently
- Quick navigation between task contexts
- Support split views and list-detail patterns
- Persistent sidebar for task/project navigation

### Choosing the Right Layout
- If users spend most time creating/editing a single artifact: document-centric
- If users juggle multiple items and switch context frequently: task-centric
- Hybrid layouts work when the primary task is document-centric but requires reference panels

## Keyboard Shortcuts

### Platform Conventions
- Follow OS standards: Ctrl+C/Cmd+C (copy), Ctrl+Z/Cmd+Z (undo), etc.
- Display shortcuts in menus and tooltips so users learn them naturally
- Provide a keyboard shortcut reference (Ctrl+/ or ? is the common convention)
- All functionality must be accessible via keyboard (accessibility requirement)

### Designing Shortcuts
- Reserve single-key shortcuts for the most frequent actions
- Use modifier keys (Ctrl/Cmd, Shift, Alt) for less frequent actions
- Group related shortcuts with the same modifier (Ctrl+Shift+* for formatting)
- Avoid conflicts with OS-level shortcuts
- Allow customization for power users

## Drag-and-Drop

- Always provide an alternative non-drag method (cut/paste, move dialog)
- Show clear drop targets with visual highlighting during drag
- Provide cursor feedback (copy vs move indicators)
- Support undo for accidental drops
- Show a ghost/preview of the dragged item
- Disable drop on invalid targets with a "not allowed" cursor

## Undo/Redo

- Support multi-level undo (minimum 20 levels)
- Make the undo stack visible when possible (edit history panel)
- Distinguish between undoable and permanent actions (warn clearly for permanent ones)
- Group related actions into single undo steps (e.g., a find-and-replace-all is one undo)
- Undo should restore the exact previous state, including selection and scroll position

## Multi-Window and Panel Management

- Allow users to resize, collapse, dock, and undock panels
- Persist layout preferences across sessions
- Provide a "Reset Layout" option for when users get lost
- Support splitting the view (side-by-side editing, comparison views)
- Minimize mode switches: keep related information visible simultaneously
- Remember window position and size between sessions

## Settings and Preferences

- Organize by category with left sidebar navigation
- Show current value of each setting (do not make users click to discover it)
- Provide search within settings for applications with many options
- Use sensible defaults so most users never need to change settings
- Distinguish application-level from document-level settings
- Support import/export of settings for team consistency

## Desktop-Specific Anti-Patterns

| Anti-Pattern | Alternative |
|-------------|-------------|
| No keyboard shortcuts | Full keyboard support with discoverable shortcuts |
| Single-level undo | Multi-level undo with visible history |
| Modal settings that reset on cancel | Apply/Cancel with intermediate preview |
| Ignoring OS conventions (custom file dialogs) | Use platform-native dialogs for file operations |
| No drag alternative | Always provide cut/paste or move dialog |
| Fixed panel layout with no customization | Dockable, collapsible, resizable panels |
| Losing window state on restart | Persist size, position, and layout between sessions |

## Acceptance Criteria Template (Desktop)

```gherkin
Feature: [Feature Name]
  # Platform: desktop ([Windows | macOS | cross-platform])
  # Key heuristics: [applicable Nielsen heuristics]

  Scenario: Keyboard workflow
    Given the user performs [task] using keyboard only
    When they use [shortcut]
    Then [expected result]
    And the shortcut is shown in the menu bar and tooltip

  Scenario: Undo support
    Given the user has performed [action]
    When they press Ctrl+Z / Cmd+Z
    Then the action is reversed
    And the redo action is available via Ctrl+Y / Cmd+Shift+Z

  Scenario: Panel management
    Given the user customizes their panel layout
    When they close and reopen the application
    Then their layout is preserved exactly
    And a Reset Layout option is available in the View menu
```
