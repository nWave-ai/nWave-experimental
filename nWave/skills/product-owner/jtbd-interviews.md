---
name: jtbd-interviews
description: JTBD interview techniques - Switch interview methodology, timeline reconstruction, Four Forces extraction, functional/emotional/social job discovery, anti-patterns, and question banks
---

# JTBD Interview Techniques

Use this skill when conducting or guiding stakeholder interviews to discover the jobs users are trying to accomplish. The Switch interview is the primary qualitative method -- it focuses on understanding why people switch between solutions.

## The Switch Interview

Developed by Bob Moesta (Re-Wired Group). Focuses on a specific moment when a customer switched from one solution to another (or decided not to switch).

### Core Protocol

- Interview customers who switched recently (ideally within 30 days)
- Focus on one specific switch event, not general opinions
- Reconstruct the timeline backward: start with the purchase, work back to first thought
- Ask about concrete past behavior, never hypotheticals
- Patterns typically emerge after 5 interviews; aim for 10 per segment
- Two-person team: one leads conversation, the other takes notes

### The Five-Stage Timeline

Reconstruct the customer's decision journey through these stages:

**Stage 1: First Thought**
The moment when the current solution first felt inadequate. Often passive and emotional rather than rational.

Key questions:
- "When did you first realize something needed to change?"
- "What was happening in your work/life at that moment?"
- "Was there a specific event or was it gradual?"

**Stage 2: Passive Looking**
Not actively seeking alternatives but noticing them incidentally. Asking friends, browsing casually, reading articles.

Key questions:
- "Before you actively started looking, what had you noticed?"
- "Did anyone mention alternatives to you?"
- "What caught your attention without you deliberately searching?"

**Stage 3: Active Looking**
Committed to the idea that change is needed. Comparing options systematically, reading reviews, requesting demos.

Key questions:
- "What made you shift from 'maybe someday' to 'I need to do this now'?"
- "What options did you consider?"
- "How did you evaluate them? What criteria mattered?"
- "What almost made you stop looking?"

**Stage 4: Deciding**
Weighing alternatives, comparing trade-offs, selecting a solution. Includes the specific trigger that moved from looking to committing.

Key questions:
- "What tipped the scale toward this specific choice?"
- "What were you most worried about?"
- "Who else was involved in the decision?"
- "What almost stopped you from deciding?"

**Stage 5: Consuming / Onboarding**
Post-switch experience. Did the new solution deliver? Any buyer's remorse? What surprised them?

Key questions:
- "What was your first experience after switching?"
- "What surprised you -- good or bad?"
- "Would you make the same choice again? Why?"
- "What do you miss from the old way?"

## Extracting the Four Forces

During the interview, map responses to the Four Forces of Progress. Each force has characteristic language patterns.

### Force 1: Push of Current Situation

What the customer says:
- "I was frustrated that..."
- "It kept breaking when..."
- "I wasted so much time on..."
- "The last straw was when..."

Interview prompts:
- "What was your biggest frustration with how things were?"
- "Tell me about the worst experience with the old approach."
- "What finally made it intolerable?"

### Force 2: Pull of New Solution

What the customer says:
- "I heard it could..."
- "I liked that it promised..."
- "My colleague said it was..."
- "I imagined being able to..."

Interview prompts:
- "What excited you about the new approach?"
- "What did you imagine your life would be like after switching?"
- "What specific promise or feature attracted you most?"

### Force 3: Anxiety of New Solution

What the customer says:
- "I was worried that..."
- "What if it doesn't..."
- "I wasn't sure I could learn..."
- "The risk was..."

Interview prompts:
- "What almost stopped you from switching?"
- "What were your biggest concerns about the new approach?"
- "What would have happened if it did not work out?"

### Force 4: Habit of Present

What the customer says:
- "I was used to..."
- "At least with the old way, I knew..."
- "I had already invested..."
- "My team was comfortable with..."

Interview prompts:
- "What did you like about the old way, despite its problems?"
- "What felt safe or familiar about staying?"
- "What would you have to give up or relearn?"

## Extracting Job Dimensions

### Functional Jobs

Surface first. The practical task.

**Questions**:
- "What were you trying to get done?"
- "Walk me through the steps you took."
- "What did 'success' look like in practical terms?"
- "What tools or resources did you use?"

### Emotional Jobs

Require deeper probing. How the customer wants to feel.

**Questions**:
- "How did that situation make you feel?"
- "What were you worried about at that point?"
- "When it worked (or failed), how did that feel?"
- "What feeling were you trying to avoid?"

### Social Jobs

Often unarticulated. How the customer wants to be perceived.

**Questions**:
- "Who else was involved or aware of this?"
- "What would your team/manager/stakeholders think?"
- "How did this affect how others saw you or your work?"
- "Was there anyone you were trying to impress or reassure?"

## Question Bank: General-Purpose

These questions work across most JTBD interviews. Adapt to context.

### Opening (build rapport, set context)
- "Take me back to the day you decided to [switch/buy/change]. What was going on?"
- "What were you doing right before that moment?"

### Timeline reconstruction
- "And then what happened?"
- "How long was it between [stage A] and [stage B]?"
- "What was happening in between?"

### Deepening
- "Can you say more about that?"
- "What do you mean by [term they used]?"
- "Why was that important to you?"
- "What would have happened if you had not done that?"

### Closing
- "Knowing what you know now, would you make the same choice?"
- "What advice would you give someone in the same situation?"
- "Is there anything I should have asked but did not?"

## Interview Anti-Patterns

| Anti-Pattern | Problem | Fix |
|--------------|---------|-----|
| Asking hypotheticals | People are poor predictors of future behavior | Ask about past events that already happened |
| Yes/no questions | Produce shallow data | Use open-ended questions: "Tell me about a time when..." |
| Leading the witness | Contaminates data | Stay neutral; do not suggest answers or validate responses |
| Treating all customers equally | Misses segmentation | Segment by switching behavior, not demographics |
| Skipping timeline reconstruction | Yields surface-level opinions | Map the complete first-thought-to-consumption journey |
| Interviewing solo | Interviewer misses details | Use two-person team: interviewer + note-taker |
| Asking about features | Gets wants, not jobs | Ask about struggles and desired progress instead |
| Rushing to solutions | Misses the real job | Spend 80% of the interview on the problem, 20% on solutions |

## Interview Output Template

After each interview, capture findings in this structure:

```markdown
## Interview: [Participant ID] -- [Date]

### Timeline
- **First Thought**: [When and what triggered awareness]
- **Passive Looking**: [What they noticed without deliberate search]
- **Active Looking**: [Trigger to active search, options considered, criteria]
- **Deciding**: [What tipped the scale, who was involved]
- **Consuming**: [First experience, surprises, regrets]

### Forces
- **Push**: [Current frustrations]
- **Pull**: [Attractions of new solution]
- **Anxiety**: [Fears about switching]
- **Habit**: [Comfort with current approach]

### Jobs Discovered
- **Functional**: [Practical task]
- **Emotional**: [Desired feeling]
- **Social**: [Desired perception]

### Key Quotes
- "[Verbatim quote that captures a force or job]"
- "[Verbatim quote that captures a force or job]"

### Patterns (update after 3+ interviews)
- [Recurring theme across interviews]
```

## Adapting for AI Product Owner Context

As an AI product owner, you do not conduct live interviews. Instead, apply JTBD interview thinking to:

1. **Requirements conversations**: When the user describes a need, probe for the timeline, forces, and job dimensions. Use the question bank to deepen understanding.
2. **Feature requests**: When the user asks for a feature, identify the push (current frustration) and pull (desired outcome). Surface anxiety and habit forces.
3. **Story discovery**: Frame discovery questions around the Switch interview stages. "What triggered this need?" maps to First Thought. "What have you tried?" maps to Active Looking.
4. **Backlog grooming**: Evaluate stories against the Four Forces. Stories driven only by Pull (shiny feature) without Push (real pain) are low-priority candidates.

## Cross-References

- For core JTBD theory and job story format: load `jtbd-core` skill
- For prioritization using opportunity scoring: load `jtbd-opportunity-scoring` skill
- For translating discoveries to BDD scenarios: load `jtbd-bdd-integration` skill
