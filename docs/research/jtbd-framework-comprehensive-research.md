# Jobs-to-be-Done (JTBD) Framework: Comprehensive Research
## Evidence-Based Analysis for AI Product Owner Agent

**Date**: 2026-02-24
**Researcher**: Nova (Evidence-Driven Knowledge Researcher)
**Research Scope**: JTBD theory, methodologies, interview techniques, software integration, and practical templates
**Overall Confidence**: High (major claims cross-verified across 3+ independent sources)
**Sources Consulted**: 20+

---

## Executive Summary

Jobs-to-be-Done (JTBD) is a theory of innovation and customer behavior that reframes product development around the progress customers seek rather than the products they buy. The central insight is that customers "hire" products and services to accomplish specific "jobs" in their lives. This research covers the four major JTBD schools of thought (Christensen, Ulwick, Klement, Moesta), interview methodologies, integration with software requirements and BDD, and practical templates for an AI product owner agent to use during requirements gathering.

Key finding: JTBD is most powerful when used to understand *why* customers switch between solutions, and this understanding directly translates into better user stories, acceptance criteria, and test scenarios. The framework complements rather than replaces personas, with JTBD driving strategic product decisions and personas informing tactical design choices.

---

## 1. Core JTBD Theory

### 1.1 Origins and Development

The JTBD framework has a dual origin. Tony Ulwick developed the foundational concept in 1991 through his Outcome-Driven Innovation (ODI) methodology at Strategyn. Clayton Christensen popularized the theory through his 2003 book *The Innovator's Solution* and later refined it in *Competing Against Luck* (2016). Christensen first articulated the theory publicly in his 2005 Harvard Business Review paper "The Cause and the Cure of Marketing Malpractice."

**Confidence**: High -- verified across Christensen Institute, Strategyn, HBR, and multiple independent sources.

**Sources**:
- [Christensen Institute -- Jobs to Be Done Theory](https://www.christenseninstitute.org/theory/jobs-to-be-done/)
- [Strategyn -- History of JTBD](https://strategyn.com/jobs-to-be-done/history-of-jtbd/)
- [HBR -- Know Your Customers' Jobs to Be Done](https://hbr.org/2016/09/know-your-customers-jobs-to-be-done)
- [GoPractice -- Jobs to Be Done Theory and Frameworks Explained](https://gopractice.io/product/jobs-to-be-done-the-theory-and-the-frameworks/)

### 1.2 The Core Insight

People do not simply buy products or services. They "hire" them to make progress in specific circumstances. A job is not about the product -- it is about the customer's struggle and desired progress. Jobs are multifaceted: they have functional, emotional, and social dimensions. The circumstances in which customers try to accomplish jobs are more critical than any buyer characteristic or demographic.

The classic example: customers do not buy a quarter-inch drill because they want a drill. They buy it because they want a quarter-inch hole. JTBD goes further: they want a quarter-inch hole because they want to hang a shelf, because they want to organize their living space, because they want to feel in control of their home.

### 1.3 Clayton Christensen's Framework

Christensen's contribution focused on the *theory* of why customers behave the way they do:

- **Jobs are stable over time**: The job of "getting from point A to point B quickly" has existed for centuries; only the solutions change
- **Jobs are solution-agnostic**: The job exists independently of any product
- **Context matters more than demographics**: A 25-year-old and a 65-year-old may have the same job in the same circumstance
- **Competition is defined by the job, not the product category**: A milkshake competes with a banana, a bagel, and boredom -- not just other milkshakes

**The Milkshake Story**: Christensen's most famous illustration involved a fast-food chain trying to improve milkshake sales. Traditional market research (demographics, taste preferences) yielded no actionable insights. By studying *when* and *why* people bought milkshakes, researchers discovered that 40% of milkshakes were purchased early in the morning by commuters. The job: "make my long, boring commute more interesting and keep me full until lunch." The milkshake competed with bananas, doughnuts, and bagels -- not other beverages.

**Source**: [HBR -- Know Your Customers' Jobs to Be Done](https://hbr.org/2016/09/know-your-customers-jobs-to-be-done)

### 1.4 Tony Ulwick's Outcome-Driven Innovation (ODI)

While Christensen provided the *theory*, Ulwick developed the *methodology* to operationalize it. ODI is a quantitative, structured process that has been tested across hundreds of Fortune 1000 innovation initiatives with a reported 86% success rate (per an independent study of Strategyn clients).

**Core ODI Principles**:

1. **The job is the unit of analysis** -- not the product, not the customer segment
2. **Needs are outcome statements** -- measurable, solution-free metrics of success
3. **A job map provides structure** -- the 8-step universal job map captures all customer needs
4. **Opportunity scoring reveals where to innovate** -- mathematical formula identifies underserved outcomes

**Outcome Statements Format**:

Every customer need in ODI is expressed as a desired outcome statement following a strict format:

```
[Direction] + the [metric] + [object of control] + [contextual clarifier]
```

Where direction is "Minimize" or "Maximize", and metric is "time," "likelihood," "number," or "frequency."

**Examples**:
- "Minimize the time it takes to determine which features are most important to users"
- "Minimize the likelihood of overlooking a critical edge case during requirements gathering"
- "Maximize the likelihood that acceptance criteria cover all relevant scenarios"
- "Minimize the number of iterations needed to reach a shared understanding of requirements"

**Outcome statements must be**:
- Solution-free (no reference to specific technology or implementation)
- Measurable (can be rated on importance and satisfaction scales)
- Controllable (the customer can assess whether the outcome improved)
- Unambiguous (interpreted the same way by all stakeholders)

**Confidence**: High -- verified across Strategyn, Wikipedia (ODI article), HBR, and multiple independent analysis sources.

**Sources**:
- [Strategyn -- Jobs-to-be-Done Comprehensive Guide](https://strategyn.com/jobs-to-be-done/)
- [Outcome-Driven Innovation -- Wikipedia](https://en.wikipedia.org/wiki/Outcome-Driven_Innovation)
- [Anthony Ulwick -- Outcome-Driven Innovation](https://anthonyulwick.com/outcome-driven-innovation/)
- [Digital Leadership -- ODI for Putting JTBD Theory into Action](https://digitalleadership.com/blog/outcome-driven-innovation/)

### 1.5 Alan Klement's "When" Framework and Job Stories

Alan Klement developed the *job story* format as a practical alternative to traditional user stories. His approach emphasizes *situation*, *motivation*, and *expected outcome* rather than *persona*, *action*, and *benefit*.

**Job Story Template**:
```
When [situation/context],
I want to [motivation/capability],
so I can [expected outcome/benefit].
```

**Key differences from user stories**:

| Aspect | User Story | Job Story |
|--------|-----------|-----------|
| Format | As a [persona], I want to [action], so that [benefit] | When [situation], I want to [motivation], so I can [outcome] |
| Focus | Who the user is | What situation triggers the need |
| Anchoring | Identity/role | Context/circumstance |
| Assumption | Users can be grouped by role | Users are grouped by situation |
| Design driver | Persona characteristics | Causality and context |

**Klement's 5 Tips for Writing Job Stories**:

1. **Refine the situation by adding contextual information**: "When I am nearly done with a document" is better than "When I want to save a document"
2. **Focus on the job, not the task**: The job is the higher-level goal; the task is one possible way to achieve it
3. **Focus on the motivation and outcome**: Do not specify the implementation ("I want a button") -- specify the motivation ("I want to be confident my work is saved")
4. **Leave the design space open**: Job stories should not prescribe solutions
5. **Reveal the forces at play**: The story should hint at push (frustration), pull (desire), anxiety (risk), and habit (comfort with current solution)

**Confidence**: High -- verified across jtbd.info (Klement's own publications), learningloop.io, multiple independent practitioner sources.

**Sources**:
- [Alan Klement -- 5 Tips for Writing a Job Story](https://jtbd.info/5-tips-for-writing-a-job-story-7c9092911fc9)
- [Learning Loop -- Job Story (JTBD)](https://learningloop.io/glossary/job-stories-jtbd)
- [Alan Klement -- Two Very Different Interpretations of JTBD](https://jtbd.info/know-the-two-very-different-interpretations-of-jobs-to-be-done-5a18b748bd89)

### 1.6 Bob Moesta's Switch Framework

Bob Moesta, co-creator of JTBD with Christensen, developed the *Switch* interview methodology and the *Forces of Progress* diagram. His approach focuses on understanding why customers switch from one solution to another.

**The Four Forces of Progress**:

```
                    PROGRESS (switching happens)
                         ^
                         |
    Push of Current  ----+---- Pull of New Solution
    Situation            |
                         |
                    NO PROGRESS (staying put)
                         ^
                         |
    Anxiety of New   ----+---- Habit of Present
    Solution             |
```

1. **Push of the Current Situation** (demand-generating): Dissatisfaction, frustration, or problems with the current solution that create motivation to change
2. **Pull of the New Solution** (demand-generating): The attractiveness, promise, or perceived benefits of an alternative that draw the customer toward switching
3. **Anxiety of the New Solution** (demand-reducing): Fear of the unknown, perceived risk, learning curve, or uncertainty about whether the new solution will actually work
4. **Habit of the Present** (demand-reducing): Familiarity, comfort, sunk costs, and inertia that make staying with the current solution easier

**Key insight**: For a switch to happen, the combined strength of Push + Pull must exceed the combined strength of Anxiety + Habit. Product teams often focus only on Pull (making their product attractive) while ignoring Anxiety and Habit reduction, which are equally critical.

**Moesta's books**:
- *Demand-Side Sales 101: Stop Selling and Help Your Customers Make Progress*
- *Learning to Build* (co-authored with Clayton Christensen)

**Confidence**: High -- verified across jobstobedone.org, Intercom blog, Re-Wired Group, and multiple independent sources.

**Sources**:
- [Jobs-to-be-Done.org -- Unpacking the Progress Making Forces Diagram](https://jobstobedone.org/radio/unpacking-the-progress-making-forces-diagram/)
- [Intercom Blog -- Bob Moesta on Jobs-to-be-Done](https://www.intercom.com/blog/podcasts/podcast-bob-moesta-on-jobs-to-be-done/)
- [Cantina -- Switching and Jobs-to-be-Done](https://cantina.co/switching-and-jobs-to-be-done-discovering-why-people-really-hire-products/)
- [Aktia Solutions -- Product Discovery with JTBD](https://aktiasolutions.com/product-discovery-with-jobs-to-be-done/)

---

## 2. JTBD Interview Techniques

### 2.1 The Switch Interview

The Switch interview, developed by Bob Moesta and the Re-Wired Group, is the primary qualitative research method in JTBD. It focuses on a specific moment when a customer switched from one solution to another (or decided not to switch).

**The Timeline**:

The interview reconstructs the customer's decision timeline through five stages:

1. **First Thought**: The moment when the current solution first felt inadequate. Something triggers awareness that "things could be better." This is often passive and emotional rather than rational.

2. **Passive Looking**: The customer is not actively seeking alternatives but notices them incidentally. They might ask friends about their experiences, browse casually, or read an article. Information intake happens without deliberate effort.

3. **Active Looking**: The customer has committed to the idea that they need a change. They compare options systematically, read reviews, request demos, and evaluate alternatives with a wide-angle lens.

4. **Deciding**: The customer consciously weighs alternatives, compares trade-offs, and selects a solution. This includes the specific trigger event that moved them from active looking to committing.

5. **Consuming / Onboarding**: Post-purchase experience. Did the new solution deliver on its promise? Did the customer experience buyer's remorse? What surprised them?

**Interview Protocol**:

- Interview customers who have switched *recently* (ideally within the last 30 days)
- Focus on *one specific switch event*, not general opinions
- Reconstruct the timeline backward: start with the purchase, then work backward to first thought
- Ask about concrete past behavior, never hypotheticals
- Aim for 10 interviews per segment; patterns typically emerge after 5
- Use a two-person team: one leads the conversation, the other takes notes

**Confidence**: High -- verified across Re-Wired Group, Dscout, Brian Rhea, multiple practitioner guides.

**Sources**:
- [The Re-Wired Group -- Top 10 JTBD Interview Tips](https://therewiredgroup.com/learn/the-top-10-jtbd-interview-tips/)
- [Dscout -- Studying Users Who Switch Products](https://dscout.com/people-nerds/switch-products-jobs-to-be-done)
- [Brian Rhea -- JTBD Interview Guide](https://brianrhea.com/jobs-to-be-done-interview-guide/)
- [Valchanova -- The Ultimate Guide to JTBD Interviews](https://valchanova.me/customer-development-jobs-to-be-done/)

### 2.2 Extracting Functional, Emotional, and Social Jobs

Every job has three dimensions that must be captured during interviews:

**Functional Jobs**: The practical task the customer is trying to accomplish. These are measurable, concrete, and typically what the customer articulates first.

- Software example: "Analyze user behavior data to identify drop-off points in the onboarding flow"
- Software example: "Deploy a new feature to production without downtime"

**Emotional Jobs**: How the customer wants to *feel* (or avoid feeling) during and after accomplishing the job. These are internal, personal, and often unarticulated.

- Software example: "Feel confident that my code changes will not break production" (emotional dimension of the deployment job)
- Software example: "Feel in control of my project timeline despite changing requirements"

**Social Jobs**: How the customer wants to be *perceived by others*. These relate to identity, status, belonging, and professional reputation.

- Software example: "Be seen as a technically competent team lead who makes sound architectural decisions"
- Software example: "Demonstrate to stakeholders that the team is delivering measurable value"

**Interview Techniques for Each Dimension**:

| Dimension | Question Patterns |
|-----------|------------------|
| Functional | "What were you trying to accomplish?" / "Walk me through what you did." |
| Emotional | "How did that make you feel?" / "What were you worried about?" |
| Social | "Who else was involved or affected?" / "What would others think?" |

**Confidence**: High -- verified across Christensen Institute, Sivo Insights, LogRocket, Stone Mantel.

**Sources**:
- [Christensen Institute -- Jobs to Be Done Theory](https://www.christenseninstitute.org/theory/jobs-to-be-done/)
- [Sivo Insights -- How to Identify Functional, Emotional, and Social Jobs](https://mrx.sivoinsights.com/blog/how-to-identify-functional-emotional-and-social-jobs-using-the-jobs-to-be-done-framework)
- [LogRocket -- Understanding the 3 Types of Jobs to Be Done](https://blog.logrocket.com/product-management/3-types-of-jobs-to-be-done/)

### 2.3 Common Interview Mistakes and Anti-Patterns

Based on research across multiple JTBD practitioners and methodologists:

1. **Confusing wants with jobs**: "I want a more intuitive UI" is a want. "Regain confidence in organizing tasks after missing a deadline" is a job. Always dig beneath surface-level feature requests.

2. **Asking about hypotheticals**: People are poor predictors of their own future behavior. Always ask about past events that have already happened, not what they "would do" in a scenario.

3. **Using yes/no questions**: Open-ended questions produce richer data. "Tell me about a time when..." is far more productive than "Did you find it frustrating?"

4. **Treating all customers as equal**: Segment by switching behavior, not demographics. Interview recent switchers, not the general customer base.

5. **Insufficient sample size**: Aim for 10 interviews per segment. Patterns emerge around interview 5, but additional interviews validate and deepen understanding.

6. **Leading the witness**: Remain neutral. Do not suggest answers or validate responses. Let the customer reconstruct their own timeline.

7. **Skipping the timeline reconstruction**: The power of JTBD interviews lies in mapping the complete first-thought-to-consumption journey. Jumping straight to opinions yields shallow data.

8. **Interviewing solo**: A two-person team (interviewer + note-taker) produces substantially better results. The interviewer can focus entirely on the conversation while the note-taker captures details and identifies follow-up opportunities.

**Confidence**: High -- verified across Re-Wired Group, GoPractice, Commoncog, multiple practitioner sources.

**Sources**:
- [Re-Wired Group -- Top 10 JTBD Interview Tips](https://therewiredgroup.com/learn/the-top-10-jtbd-interview-tips/)
- [GoPractice -- JTBD Research Interviews](https://gopractice.io/product/jtbd-interview/)
- [Commoncog -- Putting the JTBD Interview to Practice](https://commoncog.com/putting-jtbd-interview-to-practice/)
- [jtbd.info -- Top 8 Tips for JTBD Interviews](https://jtbd.info/top-8-tips-for-jtbd-interviews-6739c88f1cc9)

---

## 3. JTBD in Software Requirements

### 3.1 Job Mapping: The 8 Universal Steps

Tony Ulwick's job mapping framework reveals that all jobs follow a universal structure of eight process steps. This structure provides a systematic way to identify *all* customer needs, not just the obvious ones.

**The 8 Steps**:

| Step | Description | Software Requirements Question |
|------|-------------|-------------------------------|
| 1. **Define** | Determine goals, plan the approach, assess resources needed | "What information do users need before starting this task?" |
| 2. **Locate** | Gather necessary inputs, materials, and information | "Where do users find the data/resources they need?" |
| 3. **Prepare** | Set up the environment, organize inputs, ready for execution | "What setup or configuration is required?" |
| 4. **Confirm** | Verify readiness, validate inputs before proceeding | "How do users confirm they have everything they need?" |
| 5. **Execute** | Perform the core task | "What is the primary action sequence?" |
| 6. **Monitor** | Check progress, verify results during and after execution | "How do users know if things are working correctly?" |
| 7. **Modify** | Make adjustments, handle exceptions, course-correct | "What do users do when something goes wrong?" |
| 8. **Conclude** | Finalize, clean up, archive, and assess overall outcome | "How do users wrap up and assess success?" |

**Application to Software Requirements**:

For any feature, walk through all 8 steps to generate comprehensive requirements. Example for a feature "Deploy application to production":

1. **Define**: Determine what version to deploy, review change log, assess risk level
2. **Locate**: Find the correct build artifact, gather deployment configuration, locate rollback scripts
3. **Prepare**: Set up deployment pipeline, configure environment variables, notify stakeholders
4. **Confirm**: Run pre-deployment checks, verify build integrity, confirm deployment window
5. **Execute**: Trigger deployment, apply database migrations, update routing
6. **Monitor**: Watch health checks, verify service responses, check error rates
7. **Modify**: Roll back if errors exceed threshold, scale resources if needed, apply hotfix
8. **Conclude**: Update deployment log, notify team of completion, archive deployment artifact

Each step surfaces requirements that might otherwise be missed. The Define, Locate, and Prepare steps are particularly productive for uncovering missing requirements -- teams often jump straight to Execute without considering the full journey.

**Confidence**: High -- verified across Strategyn (originator), Sivo Insights, umbrex.com, O'Reilly.

**Sources**:
- [Strategyn -- Customer-Centered Innovation Map](https://strategyn.com/jobs-to-be-done/customer-centered-innovation-map/)
- [Strategyn -- Build Your Job Map](https://strategyn.com/jobs-to-be-done/jobs-to-be-done-playbook/build-your-job-map/)
- [Sivo Insights -- What Is a Job Map?](https://mrx.sivoinsights.com/blog/what-is-a-job-map-a-beginner-s-guide-to-jobs-to-be-done)
- [O'Reilly -- Job Mapping from The Innovator's Toolkit](https://www.oreilly.com/library/view/the-innovators-toolkit/9781118331873/9781118331873c02.xhtml)

### 3.2 Converting Jobs to User Stories and Acceptance Criteria

JTBD analysis produces artifacts at the strategic level (jobs, outcomes, forces). These must be translated into tactical development artifacts (user stories, acceptance criteria, BDD scenarios) for implementation.

**The Translation Pipeline**:

```
Job Statement (strategic)
    |
    v
Job Story (contextual)
    |
    v
User Story (implementable)
    |
    v
Acceptance Criteria (testable)
    |
    v
BDD Scenario (automatable)
```

**Step 1: Job Statement to Job Story**

Job Statement: "Help me manage the deployment risk when releasing new features"

Job Story: "When I am about to deploy a feature that touches payment processing, I want to validate that all critical paths are covered by tests, so I can deploy with confidence that revenue-generating flows will not break."

**Step 2: Job Story to User Story**

The job story reveals the *situation* and *motivation*. The user story translates this into an *implementable feature*:

User Story: "As a developer deploying to production, I want to see a test coverage report for critical paths before deployment, so that I can verify all revenue-critical flows are tested."

**Step 3: User Story to Acceptance Criteria**

Acceptance criteria make the user story *testable*:

- Test coverage for payment processing module is at least 90%
- Coverage report highlights any critical paths with less than 80% coverage
- Deployment is blocked if any critical path has zero test coverage
- Report is generated automatically as part of the deployment pipeline

**Key differences in translation**:

| Level | Focuses On | Solution-Specific? | Testable? |
|-------|-----------|--------------------| ----------|
| Job Statement | Why the customer needs progress | No | No |
| Job Story | Situation and motivation | No | No |
| User Story | Feature to implement | Yes (bounded) | Partially |
| Acceptance Criteria | Verifiable conditions | Yes | Yes |

**Sources**:
- [Mountain Goat Software -- Job Stories as Alternative to User Stories](https://www.mountaingoatsoftware.com/blog/job-stories-offer-a-viable-alternative-to-user-stories)
- [airfocus -- User Stories vs JTBD](https://airfocus.com/product-learn/user-stories-vs-jtbd/)
- [ORIL -- Job Stories vs User Stories](https://oril.co/blog/job-stories-vs-user-stories/)

### 3.3 Opportunity Scoring: Prioritizing Features

Ulwick's Opportunity Algorithm provides a quantitative method for prioritizing features based on customer-defined metrics:

**Formula**:
```
Opportunity Score = Importance + max(0, Importance - Satisfaction)
```

Where:
- **Importance** = percentage of customers rating an outcome as "very important" or "extremely important" (on a 1-5 scale, those rating 4 or 5)
- **Satisfaction** = percentage of customers rating their current satisfaction with the outcome as "very satisfied" or "extremely satisfied"
- Scale: 0-20 (higher = greater opportunity)

**Interpretation**:

| Score Range | Interpretation | Action |
|-------------|---------------|--------|
| 15-20 | Extremely underserved | High-priority opportunity; invest heavily |
| 12-15 | Underserved | Strong opportunity; plan for next release |
| 10-12 | Appropriately served | Maintain current level; incremental improvement |
| < 10 | Overserved | Potential to simplify; may be over-engineered |

**Application to Software Prioritization**:

Survey users on outcome statements derived from job mapping. For example:

| Outcome Statement | Importance | Satisfaction | Opportunity Score |
|-------------------|-----------|-------------|-------------------|
| Minimize the time to identify the root cause of a production issue | 92% | 35% | 92 + (92-35) = 149 (14.9 normalized) |
| Minimize the likelihood of deploying untested code | 88% | 72% | 88 + (88-72) = 104 (10.4 normalized) |
| Minimize the time to onboard a new team member | 65% | 40% | 65 + (65-40) = 90 (9.0 normalized) |

The first outcome (root cause identification) represents the biggest opportunity -- high importance, low satisfaction.

**Confidence**: High -- verified across Strategyn, Wikipedia, Marketing Journal, multiple independent analyses.

**Sources**:
- [Strategyn -- Jobs-to-be-Done](https://strategyn.com/jobs-to-be-done/)
- [Marketing Journal -- The Opportunity Algorithm](https://www.marketingjournal.org/the-path-to-growth-the-opportunity-algorithm-anthony-ulwick/)
- [airfocus -- What Is Opportunity Scoring?](https://airfocus.com/glossary/what-is-opportunity-scoring/)
- [Notes for Growth -- What is the Opportunity Score?](https://notesforgrowth.github.io/Opportunity-Score/)

### 3.4 JTBD vs Personas: When Each Is Appropriate

JTBD and personas are complementary frameworks, not competing ones. Research from Nielsen Norman Group and multiple practitioners supports using both in the right contexts.

**When to Use JTBD**:
- Defining product strategy and vision
- Discovering new market opportunities
- Understanding why customers switch solutions
- Identifying unmet needs across customer segments
- Prioritizing features by outcome importance
- Early-stage product development (before detailed design)

**When to Use Personas**:
- Detailed UX/UI design decisions
- Building empathy across cross-functional teams
- Identifying pain points in existing user journeys
- Communication with stakeholders who think in customer profiles
- Content strategy and messaging

**When to Use Both Together**:
- Personas identify *who* the user is and what pain points they experience
- JTBD identifies *what progress* they are trying to make and *why*
- Together: "Sarah (persona: startup CTO, non-technical background) is trying to (job: deploy reliable software without deep DevOps expertise) because (outcome: she needs to ship features fast without hiring a dedicated ops team)"

**Confidence**: High -- verified across Nielsen Norman Group, thrv.com, delve.ai, multiple independent sources.

**Sources**:
- [Nielsen Norman Group -- Personas vs. Jobs-to-Be-Done](https://www.nngroup.com/articles/personas-jobs-be-done/)
- [thrv -- JTBD vs Personas: The Ultimate Guide](https://www.thrv.com/blog/jobs-to-be-done-vs-personas-the-ultimate-guide-to-unified-customer-understanding-in-product-development)
- [Delve.ai -- Personas and Jobs to Be Done](https://www.delve.ai/blog/personas-jobs-to-be-done)

---

## 4. JTBD Integration with BDD and Acceptance Testing

### 4.1 From Job Stories to Given-When-Then Scenarios

Job stories translate naturally into BDD scenarios because both frameworks emphasize *context* (situation/given), *action* (motivation/when), and *outcome* (expected result/then).

**Translation Pattern**:

```
Job Story:
  When [situation],
  I want to [motivation],
  so I can [outcome].

BDD Scenario:
  Given [the situation described in the job story],
  When [the user takes action aligned with the motivation],
  Then [the outcome is achieved or measurable].
```

**Worked Example**:

Job Story: "When I receive an alert that a production service is degraded, I want to see the most likely root cause with supporting evidence, so I can begin remediation within minutes instead of hours."

BDD Scenarios:

```gherkin
Scenario: Identify root cause from service degradation alert
  Given the monitoring system has detected degraded response times on the payment service
  And the degradation started 5 minutes ago
  When the operator opens the incident dashboard
  Then the system displays the top 3 probable root causes ranked by likelihood
  And each root cause includes supporting metrics and log evidence
  And the most likely root cause is displayed within 10 seconds

Scenario: Enable rapid remediation from root cause analysis
  Given the operator has identified the root cause as a database connection pool exhaustion
  When the operator selects the recommended remediation action
  Then the system presents a runbook with step-by-step remediation instructions
  And the estimated time to remediate is displayed
  And the operator can execute the first remediation step directly from the dashboard
```

### 4.2 Using JTBD to Identify Missing Test Scenarios

JTBD analysis systematically reveals test scenarios that pure feature-driven development misses. The key technique is to apply the Four Forces and the 8-Step Job Map to each feature.

**Forces-Based Test Discovery**:

For each feature, ask:

| Force | Test Question | Example Scenario |
|-------|--------------|------------------|
| Push | What frustration drove the user to this feature? | "Given the user has experienced 3 failed deployments this week..." |
| Pull | What outcome is the user hoping for? | "Then the deployment success rate improves to 95%+" |
| Anxiety | What could go wrong with the new solution? | "Given the user is unsure whether rollback works correctly..." |
| Habit | What existing workflow might resist adoption? | "Given the user is accustomed to manual deployment via SSH..." |

**Job-Map-Based Test Discovery**:

Walk through all 8 steps for the feature and write at least one test per step:

| Step | Missing Scenario Pattern |
|------|------------------------|
| Define | "What if the user does not have enough information to start?" |
| Locate | "What if required inputs are not available or are stale?" |
| Prepare | "What if the setup fails or the environment is misconfigured?" |
| Confirm | "What if validation passes incorrectly (false positive)?" |
| Execute | "What if execution is interrupted midway?" |
| Monitor | "What if monitoring reports misleading success?" |
| Modify | "What if the modification makes things worse?" |
| Conclude | "What if cleanup fails silently?" |

**Confidence**: Medium-High -- the JTBD-to-BDD translation is a synthesis based on established patterns from both frameworks. Direct peer-reviewed sources on this specific integration are limited, but the logical mapping is well-supported by practitioners.

**Sources**:
- [SAFe Framework -- Behavior-Driven Development](https://framework.scaledagile.com/behavior-driven-development)
- [Thoughtbot -- Applying JTBD Theory to Build Successful Products](https://thoughtbot.com/playbook/rapid-product-validation/jtbd)
- [airfocus -- User Stories vs JTBD](https://airfocus.com/product-learn/user-stories-vs-jtbd/)

---

## 5. Practical Patterns and Templates

### 5.1 Job Story Template

```markdown
## Job Story: [Descriptive Title]

**When** [specific situation or triggering context],
**I want to** [motivation -- what the user needs to do or achieve],
**so I can** [expected outcome -- the progress they want to make].

### Functional Job
[The practical task to accomplish]

### Emotional Job
[How the user wants to feel]

### Social Job
[How the user wants to be perceived]

### Forces Analysis
- **Push**: [What frustration with current solution drives this?]
- **Pull**: [What about the new solution attracts them?]
- **Anxiety**: [What fears or risks might prevent adoption?]
- **Habit**: [What existing behaviors resist change?]

### Outcome Statements
1. Minimize the [metric] it takes to [desired outcome]
2. Minimize the likelihood of [undesired outcome]
3. Maximize the [metric] of [desired quality]
```

### 5.2 Forces Diagram Template

```markdown
## Forces Diagram: [Feature/Decision]

### Demand-Generating Forces (driving change)

**Push of Current Situation**:
- [ ] [Specific frustration #1]
- [ ] [Specific frustration #2]
- [ ] [Specific frustration #3]

**Pull of New Solution**:
- [ ] [Specific attraction #1]
- [ ] [Specific attraction #2]
- [ ] [Specific attraction #3]

### Demand-Reducing Forces (resisting change)

**Anxiety of New Solution**:
- [ ] [Specific fear #1]
- [ ] [Specific fear #2]
- [ ] [Specific fear #3]

**Habit of Present**:
- [ ] [Specific habit #1]
- [ ] [Specific habit #2]
- [ ] [Specific habit #3]

### Assessment
- **Switch likelihood**: [High/Medium/Low]
- **Key blocker**: [The strongest demand-reducing force]
- **Key enabler**: [The strongest demand-generating force]
- **Design implication**: [What the product must do to tip the balance]
```

### 5.3 Opportunity Scoring Matrix Template

```markdown
## Opportunity Scoring Matrix: [Product/Feature Area]

| # | Outcome Statement | Importance (%) | Satisfaction (%) | Opportunity Score | Priority |
|---|-------------------|---------------|-----------------|-------------------|----------|
| 1 | Minimize the time it takes to [outcome] | | | | |
| 2 | Minimize the likelihood of [undesired outcome] | | | | |
| 3 | Maximize the [quality] when [context] | | | | |

### Scoring Method
- **Importance**: % of respondents rating 4 or 5 on a 5-point importance scale
- **Satisfaction**: % of respondents rating 4 or 5 on a 5-point satisfaction scale
- **Opportunity Score**: Importance + max(0, Importance - Satisfaction)
- **Priority**: Extremely Underserved (15+), Underserved (12-15), Served (10-12), Overserved (<10)

### Top Opportunities (Score >= 12)
1. [Outcome] -- Score: [X], Implication: [Y]
2. [Outcome] -- Score: [X], Implication: [Y]

### Overserved Areas (Score < 10) -- Simplification Candidates
1. [Outcome] -- Score: [X], Implication: [Y]
```

### 5.4 Job Map Template

```markdown
## Job Map: [Job Statement]

### 1. DEFINE
- What goals must the user define before starting?
- What planning or assessment is needed?
- **Needs**: [outcome statements for this step]

### 2. LOCATE
- What inputs, data, or resources must the user gather?
- Where do they find these resources?
- **Needs**: [outcome statements for this step]

### 3. PREPARE
- What setup or configuration is required?
- How does the user organize inputs for the task?
- **Needs**: [outcome statements for this step]

### 4. CONFIRM
- How does the user verify readiness?
- What validations must pass before proceeding?
- **Needs**: [outcome statements for this step]

### 5. EXECUTE
- What is the core action sequence?
- What decisions must be made during execution?
- **Needs**: [outcome statements for this step]

### 6. MONITOR
- How does the user track progress?
- What signals indicate success or failure?
- **Needs**: [outcome statements for this step]

### 7. MODIFY
- What adjustments might be needed?
- How does the user handle exceptions?
- **Needs**: [outcome statements for this step]

### 8. CONCLUDE
- How does the user finalize and wrap up?
- What archiving, logging, or assessment occurs?
- **Needs**: [outcome statements for this step]
```

### 5.5 JTBD-to-BDD Translation Template

```markdown
## JTBD-to-BDD Translation: [Feature Name]

### Source Job Story
When [situation],
I want to [motivation],
so I can [outcome].

### Derived BDD Scenarios

#### Happy Path
```gherkin
Scenario: [Outcome achieved successfully]
  Given [situation from job story]
  And [necessary preconditions]
  When [user action aligned with motivation]
  Then [outcome from job story is measurable]
  And [emotional job is addressed]
```

#### Anxiety Path (addressing fears)
```gherkin
Scenario: [New solution handles user's anxiety]
  Given [user has specific anxiety about new approach]
  When [anxiety-triggering event occurs]
  Then [system provides reassurance or safety net]
  And [user can recover without data loss or downtime]
```

#### Habit Path (easing transition)
```gherkin
Scenario: [Existing workflow user transitions smoothly]
  Given [user is accustomed to previous workflow]
  When [user encounters the new approach]
  Then [familiar patterns are preserved where possible]
  And [new capabilities are discoverable without disruption]
```

#### Edge Cases (from job map steps)
```gherkin
Scenario: [Define step -- insufficient information]
  Given [user lacks necessary context to begin]
  When [user attempts to start the job]
  Then [system guides user to gather missing information]

Scenario: [Monitor step -- misleading feedback]
  Given [execution appears successful but has hidden issues]
  When [user checks results]
  Then [system surfaces potential problems proactively]
```
```

### 5.6 AI Product Owner JTBD Analysis Checklist

This checklist is designed for an AI agent conducting JTBD analysis during requirements gathering:

```markdown
## JTBD Analysis Checklist

### Phase 1: Job Discovery
- [ ] Identify the core job the user is trying to accomplish
- [ ] Express the job in solution-agnostic language
- [ ] Identify functional, emotional, and social dimensions
- [ ] Map the job to the 8-step universal job map
- [ ] Generate outcome statements for each job map step

### Phase 2: Forces Analysis
- [ ] Identify push forces (current frustrations)
- [ ] Identify pull forces (attraction of new solution)
- [ ] Identify anxiety forces (fears about the new approach)
- [ ] Identify habit forces (inertia of current approach)
- [ ] Assess net force balance (will switching happen?)

### Phase 3: Requirements Translation
- [ ] Write job stories in When/Want/Can format
- [ ] Derive user stories from each job story
- [ ] Write acceptance criteria for each user story
- [ ] Translate to BDD Given-When-Then scenarios
- [ ] Include anxiety and habit scenarios (not just happy path)

### Phase 4: Prioritization
- [ ] Rate outcome statements on importance (1-5)
- [ ] Rate outcome statements on current satisfaction (1-5)
- [ ] Calculate opportunity scores
- [ ] Rank features by opportunity score
- [ ] Identify overserved areas (simplification candidates)

### Phase 5: Validation
- [ ] Verify job stories describe situations, not personas
- [ ] Verify outcome statements are solution-free
- [ ] Verify acceptance criteria cover all 8 job map steps
- [ ] Verify forces analysis addresses anxiety reduction
- [ ] Cross-reference with existing user research data
```

---

## 6. Knowledge Gaps and Limitations

### 6.1 Documented Gaps

1. **Quantitative validation of JTBD in software specifically**: While JTBD has strong evidence in physical product innovation (Strategyn's 86% success rate), peer-reviewed studies specifically measuring JTBD's impact on software product success rates are limited. Most software-specific evidence is anecdotal or from case studies rather than controlled studies.

2. **JTBD-to-BDD integration methodology**: The translation from job stories to BDD scenarios is a practitioner synthesis. No single authoritative source provides a complete, validated methodology for this specific integration. The pattern described in Section 4 is derived from first principles of both frameworks.

3. **Opportunity scoring in agile contexts**: Ulwick's opportunity scoring assumes large-scale quantitative surveys (100+ respondents). Adaptation of this methodology for small agile teams with limited access to users is not well-documented in the literature.

4. **Alan Klement vs Tony Ulwick disagreements**: There is documented tension between Klement's interpretation of JTBD (situation-focused, qualitative) and Ulwick's (outcome-focused, quantitative). Ulwick has publicly critiqued Klement's approach as a departure from the original framework. Users of this research should be aware that these are two distinct schools that do not fully agree on methodology.

### 6.2 Source Limitations

- Several key sources (jtbd.info, jobs-to-be-done.com) are authored by JTBD practitioners who have commercial interests in promoting the framework
- The Strategyn 86% success rate claim comes from a study conducted with Strategyn's own clients, introducing potential selection bias
- Bob Moesta's and Chris Spiek's interview methodology is primarily transmitted through workshops and podcasts rather than published, peer-reviewed papers

---

## 7. Recommended Reading

| Title | Author(s) | Focus |
|-------|-----------|-------|
| *Competing Against Luck* | Clayton Christensen et al. | JTBD theory and case studies |
| *Jobs to be Done: Theory to Practice* | Anthony Ulwick | ODI methodology, outcome statements, job mapping |
| *When Coffee and Kale Compete* | Alan Klement | Job stories, situation-driven design (free PDF available) |
| *Demand-Side Sales 101* | Bob Moesta | Switch interviews, forces diagram |
| *Intercom on Jobs-to-be-Done* | Intercom team | Practical JTBD for software (free ebook) |
| *The Innovator's Dilemma* | Clayton Christensen | Disruption theory (JTBD precursor) |

---

## Source Registry

| # | Source | Domain | Reputation Tier | Accessed |
|---|--------|--------|----------------|----------|
| 1 | Christensen Institute | christenseninstitute.org | Industry Leader | 2026-02-24 |
| 2 | Harvard Business Review | hbr.org | Academic/Industry | 2026-02-24 |
| 3 | Strategyn | strategyn.com | Industry Leader | 2026-02-24 |
| 4 | Nielsen Norman Group | nngroup.com | Industry Leader | 2026-02-24 |
| 5 | GoPractice | gopractice.io | Medium-High | 2026-02-24 |
| 6 | Re-Wired Group | therewiredgroup.com | Industry Leader | 2026-02-24 |
| 7 | Intercom Blog | intercom.com | Industry Leader | 2026-02-24 |
| 8 | Wikipedia (ODI) | wikipedia.org | Medium-High | 2026-02-24 |
| 9 | jtbd.info (Klement) | jtbd.info | Medium-High | 2026-02-24 |
| 10 | Mountain Goat Software | mountaingoatsoftware.com | Industry Leader | 2026-02-24 |
| 11 | SAFe Framework | scaledagile.com | Industry Leader | 2026-02-24 |
| 12 | Thoughtbot | thoughtbot.com | Industry Leader | 2026-02-24 |
| 13 | airfocus | airfocus.com | Medium-High | 2026-02-24 |
| 14 | Sivo Insights | sivoinsights.com | Medium-High | 2026-02-24 |
| 15 | LogRocket | logrocket.com | Medium-High | 2026-02-24 |
| 16 | Dscout | dscout.com | Medium-High | 2026-02-24 |
| 17 | Brian Rhea | brianrhea.com | Medium | 2026-02-24 |
| 18 | Valchanova | valchanova.me | Medium | 2026-02-24 |
| 19 | Marketing Journal | marketingjournal.org | Medium-High | 2026-02-24 |
| 20 | Anthony Ulwick | anthonyulwick.com | Industry Leader | 2026-02-24 |
| 21 | Commoncog | commoncog.com | Medium-High | 2026-02-24 |
| 22 | ORIL | oril.co | Medium | 2026-02-24 |
| 23 | Cantina | cantina.co | Medium-High | 2026-02-24 |
| 24 | Digital Leadership | digitalleadership.com | Medium-High | 2026-02-24 |
| 25 | O'Reilly | oreilly.com | Industry Leader | 2026-02-24 |
