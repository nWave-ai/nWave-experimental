---
name: ux-emotional-design
description: Emotional design and delight patterns for product owners. Load when designing onboarding flows, empty states, first-run experiences, or evaluating the emotional quality of an interface.
---

# Emotional Design and Delight

Patterns for creating interfaces that feel good to use. Use during discovery to map emotional arcs and during requirements to specify delight moments.

## Walter's Hierarchy of User Needs

Four layers that must be satisfied in order (bottom to top):

```
        /\
       /  \
      / PL \     4. PLEASURABLE - Delight, surprise, emotional connection
     /------\
    / USABLE \    3. USABLE - Easy to learn, intuitive, efficient
   /----------\
  / RELIABLE   \   2. RELIABLE - Consistent, dependable, no crashes
 /--------------\
/ FUNCTIONAL     \  1. FUNCTIONAL - It works, serves its purpose
------------------
```

**Key insight**: A product can be delightful only if it is usable. Beautiful animations on a buggy, confusing interface make things worse. Invest in the foundation before the polish.

### Applying the Hierarchy in Requirements
- Phase 1 stories: ensure functionality works correctly
- Phase 2 stories: add reliability (error handling, edge cases, recovery)
- Phase 3 stories: improve usability (simplify flows, reduce steps)
- Phase 4 stories: add delight (only after the above are solid)

## Surface Delight vs Deep Delight

### Surface Delight (momentary, contextual)
- Playful animations on interaction
- Witty microcopy in messages
- Surprising easter eggs
- Visually pleasing illustrations

### Deep Delight (sustained, holistic)
- The interface anticipates what the user needs next
- Complex tasks feel effortless
- Users achieve flow state: immersed productivity without obstruction
- The tool becomes an extension of the user's thinking

**Prioritization rule**: Deep delight generates loyalty and return usage. Surface delight creates momentary positive reactions but cannot compensate for usability failures. Invest in deep delight first.

### Requirements Implications
- "The system suggests the most likely next action" (deep delight) is higher priority than "The save button has a satisfying animation" (surface delight)
- Stories about reducing steps, anticipating needs, and removing friction are delight stories even if they do not feel "fun"

## Empty States

Empty states (no data, first use, zero results) are opportunities, not dead ends.

### Good Empty State Design
- Explain what will appear when there is content
- Provide a clear call to action to create the first item
- Use illustration or visual interest to make the state feel intentional
- Offer guidance or templates for first-time users

### Anti-Pattern
A blank page with no guidance, or "No results found" with no suggested next step.

### Empty State Checklist for Requirements
- [ ] First-time empty state has onboarding guidance
- [ ] Search empty state suggests alternative queries or filters
- [ ] Error empty state explains what happened and how to recover
- [ ] Each empty state has a primary call to action

## Onboarding and First-Run Experience

### Progressive Onboarding (preferred)
- Let users start real work immediately
- Introduce features in context, at the moment they become relevant
- Use tooltips and inline hints that dismiss after first use
- Offer a "skip" option for experienced users
- Celebrate the first successful action

### Anti-Pattern
A mandatory 8-step walkthrough that blocks users from doing anything before completing it.

### Onboarding Patterns by Platform

**Web**: Inline hints, contextual tooltips, sample data to explore, "getting started" checklist widget.

**Desktop**: First-run wizard for essential setup only (account, preferences), then contextual hints during use.

**CLI**: First command outputs a welcome message with 2-3 example commands. `--help` is comprehensive. Config file created with sensible defaults and comments.

## Tone of Voice in UI Copy

### Principles
- Be clear first, clever second
- Use active voice and present tense
- Address the user as "you"
- Keep instructions to 1-2 sentences
- A consistent voice builds trust; an inconsistent voice creates unease

### Matching Tone to Context

| Context | Tone | Example |
|---------|------|---------|
| Error message | Empathetic, helpful | "We could not save your changes. Check your connection and try again." |
| Success message | Encouraging, brief | "Project created. You are ready to start." |
| Empty state | Inviting, guiding | "No projects yet. Create your first one to get started." |
| Destructive action | Clear, serious | "This will permanently delete 3 files. This cannot be undone." |
| Loading/waiting | Reassuring | "Setting things up. This usually takes about 30 seconds." |
| Neutral action | Straightforward | "Select a template." |

### When Personality Helps vs When It Annoys

**Personality helps when**:
- The user is not stressed (onboarding, success states, empty states)
- The moment is low-stakes
- The brand voice is well-established and consistent

**Personality annoys when**:
- The user is frustrated (error states, failures)
- The user is in a hurry (critical workflows, high-frequency tasks)
- The humor is forced or inconsistent with the rest of the interface
- Cleverness obscures the message

## Microinteractions That Create Delight

### High-Value Microinteractions
- Pull-to-refresh with a satisfying animation
- Skeleton screens instead of blank loading states
- Smooth transitions between states (not abrupt swaps)
- Smart defaults that reduce typing
- Autocomplete that learns from usage patterns
- Undo toast after destructive actions ("Deleted. Undo?")

### Low-Value Microinteractions (skip these)
- Decorative loading animations that add no information
- Sound effects for routine actions
- Excessive bounce or wobble animations
- Easter eggs that interfere with the workflow

### Requirements Pattern for Microinteractions
When specifying a microinteraction in acceptance criteria:
- State the trigger (what the user does)
- State the feedback (what the user sees/feels)
- State the purpose (why this interaction matters for the experience)

Example: "When the user drags a card to a new column, the card smoothly animates to its new position and the column header count updates, confirming the move was successful."

## Emotional Arc Integration

When mapping emotional arcs during journey discovery, use these reference points:

| Journey Phase | Target Emotion | Design Lever |
|--------------|----------------|--------------|
| First encounter | Curious, welcomed | Clear value proposition, inviting empty state |
| Setup/config | Confident, guided | Progressive onboarding, sensible defaults |
| First success | Accomplished, delighted | Celebration moment, clear confirmation |
| Regular use | Efficient, in flow | Shortcuts, anticipation, minimal friction |
| Error/failure | Supported, not blamed | Empathetic copy, clear recovery path |
| Completion | Satisfied, proud | Summary of accomplishment, next steps |

Use this table when asking emotional arc questions during discovery. Map each journey step to a target emotion and identify the design lever that achieves it.
