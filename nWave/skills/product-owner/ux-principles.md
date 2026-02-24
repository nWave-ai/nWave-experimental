---
name: ux-principles
description: Core UX principles for product owners. Load when evaluating interface designs, writing acceptance criteria with UX requirements, or reviewing wireframes and mockups.
---

# UX Principles

Evidence-based UX fundamentals for guiding interface design during requirements gathering. Use these principles to evaluate designs, write better acceptance criteria, and ask the right questions during discovery.

## Nielsen's 10 Usability Heuristics

Apply these when reviewing any interface design or writing acceptance criteria.

| # | Heuristic | Product Owner Action |
|---|-----------|---------------------|
| 1 | **Visibility of system status** | Require feedback for every user action within 100ms. Status indicators for all async operations. |
| 2 | **Match between system and real world** | Ban internal jargon from UI. Use domain language from user research. |
| 3 | **User control and freedom** | Every destructive action needs undo or confirmation. Navigation always allows going back. |
| 4 | **Consistency and standards** | Require a design system. Audit for inconsistent terminology across features. |
| 5 | **Error prevention** | Require input validation, constraints, and confirmation for irreversible actions. |
| 6 | **Recognition over recall** | Prefer dropdowns over free text when options are known. Show recent items. Provide contextual help. |
| 7 | **Flexibility and efficiency** | Require keyboard shortcuts for frequent actions. Support both mouse and keyboard workflows. |
| 8 | **Aesthetic and minimalist design** | Challenge every UI element: does it serve the user's current task? Remove decorative clutter. |
| 9 | **Help with errors** | Error messages state what happened, why, and what to do next. No raw error codes. |
| 10 | **Help and documentation** | Require contextual help (tooltips, inline guidance). Documentation structured by task, not feature. |

### Heuristic Evaluation Questions

For each screen or workflow under review:

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

Score each 0 (no problem) to 4 (usability catastrophe). Fix 3s and 4s before launch.

## Don Norman's Design Principles

Six principles that explain why some interfaces feel intuitive.

**Affordances**: What actions an object allows. Digital affordances must be made visible through design since screens lack physical properties. A button affords clicking; a slider affords dragging.

**Signifiers**: Visual indicators that communicate where and how to act. A blue underlined word signifies "clickable." Affordances define possibility; signifiers make it discoverable.

**Mapping**: The relationship between controls and effects. Natural mapping uses spatial correspondence (volume slider goes up to increase). Poor mapping forces memorization.

**Feedback**: Every user action must produce perceptible feedback. Silence after an action is the most common source of user confusion. Feedback must be immediate, informative, and proportional.

**Constraints**: Limitations that guide correct action. Graying out unavailable options (logical), red means stop (cultural), a USB plug fits one way (physical).

**Conceptual Models**: The mental image users form about how the system works. When the user's model matches the system model, the interface feels intuitive. Build accurate models through visible structure and consistent behavior.

### Applying Norman's Principles in Requirements

- For every interactive element: what does it afford? How is that signified?
- For every control: is the mapping between action and effect natural?
- For every action: what feedback confirms it worked?
- For every error path: what constraints could prevent the error?

## Cognitive Load Laws

Three laws governing how humans process information in interfaces.

### Fitts's Law
Time to reach a target depends on distance and size.

- Make primary action buttons large and close to the cursor's likely position
- Place destructive actions away from constructive ones
- Screen edges are easy targets (infinite edge) -- use them for important controls
- Minimum touch targets: 44x44px (Apple) or 48x48dp (Material Design)

### Hick's Law
Decision time increases with the number and complexity of choices.

- Limit primary navigation to 5-7 items
- Use progressive disclosure to hide advanced options
- Break complex decisions into smaller sequential steps
- Highlight recommended options to reduce decision paralysis

### Miller's Law
Working memory holds approximately 7 (plus or minus 2) items.

- Chunk information into groups of 3-5 items
- Use visual grouping (cards, sections, whitespace) to aid scanning
- Do not require users to remember information across pages
- Display codes and numbers in chunks (phone numbers, credit cards)

## Progressive Disclosure

Resolves the tension between simplicity for novices and power for experts.

**Core rule**: Show the most important options first. Reveal specialized options on request.

**Two success factors**:
1. Correctly splitting features between initial and secondary views (requires user research)
2. Making the path to advanced features obvious through visible, well-labeled controls

**Design limits**: Most interfaces work best with a maximum of two disclosure levels. Three or more causes disorientation.

**Distinct from wizards**: Progressive disclosure uses hierarchical navigation (return to initial view). Wizards use linear sequences through steps.

## Accessibility Essentials (WCAG 2.2 AA)

Four principles (POUR) -- the minimum a product owner must require.

| Principle | Key Requirements |
|-----------|-----------------|
| **Perceivable** | Text alternatives for images, captions for video, 4.5:1 contrast ratio, text resizable to 200% |
| **Operable** | Full keyboard operation, no keyboard traps, adequate time limits |
| **Understandable** | Readable text, predictable behavior, input assistance and error identification |
| **Robust** | Valid semantic HTML, ARIA roles where needed, screen reader compatibility |

### Product Owner Minimums

- 4.5:1 contrast ratio for normal text, 3:1 for large text
- All functionality accessible via keyboard
- Focus indicators visible on all interactive elements
- Minimum target size of 24x24 CSS pixels
- Form inputs have associated labels
- Error messages identify the field and suggest correction
- Page has a descriptive title

## UX Review Checklist

Use when reviewing designs or writing acceptance criteria.

### Visibility and Feedback
- [ ] Every user action produces visible feedback within 100ms
- [ ] Loading states shown for operations >1 second
- [ ] Success confirmations for state-changing actions
- [ ] Error states communicated with recovery guidance

### Navigation and Orientation
- [ ] User can answer: Where am I? Where can I go? How do I get back?
- [ ] Primary navigation has 7 or fewer items

### Cognitive Load
- [ ] Choices per decision point <= 7
- [ ] Information chunked into scannable groups
- [ ] Progressive disclosure hides advanced options
- [ ] No requirement to remember info across pages

### Accessibility
- [ ] Contrast ratio >= 4.5:1 for text
- [ ] All functionality accessible via keyboard
- [ ] Focus indicators visible
- [ ] Touch/click targets >= 24x24px
- [ ] Form fields have associated labels

### Consistency
- [ ] Same action looks and behaves the same everywhere
- [ ] Terminology is consistent throughout
- [ ] Platform conventions are followed
