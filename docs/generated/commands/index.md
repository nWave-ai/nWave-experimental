# Commands

| Command | Description | Arguments |
| --- | --- | --- |
| `/nw:deliver` | Execute complete DELIVER wave: roadmap \u2192 execute-all \u2192 finalize | [feature-description] - Example: "Implement user authentication with JWT" |
| `/nw:design` | Architecture design with visual representation | [component-name] - Optional: --architecture=[hexagonal|layered|microservices] --diagram-format=[mermaid|plantuml] |
| `/nw:devops` | Platform readiness, CI/CD, infrastructure, and deployment design | [deployment-target] - Optional: --environment=[staging|production] --validation=[full|smoke] |
| `/nw:diagram` | Architecture diagram management | [diagram-type] - Optional: --format=[mermaid|plantuml|c4] --level=[context|container|component] |
| `/nw:discover` | Evidence-based product discovery and market validation | [product-concept] - Optional: --interview-depth=[overview|comprehensive] --output-format=[md|yaml] |
| `/nw:discuss` | UX journey design, requirements gathering, and business analysis | [feature-name] - Optional: --phase=[journey|requirements] --interactive=[high|moderate] --output-format=[md|yaml] |
| `/nw:distill` | Acceptance test creation and business validation | [story-id] - Optional: --test-framework=[cucumber|specflow|pytest-bdd] --integration=[real-services|mocks] |
| `/nw:document` | Create evidence-based DIVIO-compliant documentation | [topic/component] - Optional: --type=[tutorial|howto|reference|explanation] --research-depth=[overview|detailed|comprehensive|deep-dive] |
| `/nw:execute` | Execute atomic task with state tracking | [agent] [step-id] - Example: @software-crafter "01-01" |
| `/nw:finalize` | Summarize achievements, archive to docs/evolution, clean up feature files | [agent] [project-id] - Example: @platform-architect "auth-upgrade" |
| `/nw:forge` | Create and validate new specialized agents | [agent-name] - Optional: --type=[specialist|reviewer|orchestrator] --pattern=[react|reflection|router] |
| `/nw:mikado` | [EXPERIMENTAL] Complex refactoring roadmaps with visual tracking | [refactoring-goal] - Optional: --complexity=[simple|moderate|complex] --visualization=[tree|graph] |
| `/nw:mutation-test` | Mutation testing quality gate for test suite validation | [project-id] - Optional: --threshold=[75|80|85] --language=[auto|python|java|javascript] |
| `/nw:refactor` | Systematic refactoring with Mikado Method | [target-class-or-module] - Optional: --level=[1-6] --method=[extract|inline|rename|move] --scope=[method|class|module] |
| `/nw:research` | Evidence-driven knowledge research with source verification | [topic] - Optional: --research_depth=[overview|detailed|comprehensive|deep-dive] --skill-for=[agent-name] |
| `/nw:review` | Expert critique and quality review - Types: roadmap, step, task, implementation | [agent] [artifact-type] [artifact-path] - Example: @software-crafter task "roadmap.yaml" |
| `/nw:roadmap` | Create comprehensive planning document | [agent] [goal-description] - Example: @solution-architect "Migrate to microservices" |
| `/nw:root-why` | Root cause analysis and debugging | [problem-description] - Optional: --depth=[3|5|7-whys] --output=[text|diagram|report] |
