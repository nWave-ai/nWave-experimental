---
name: nw-new
description: "Routes a new request to the earliest authority that lacks evidence, without creating a feature workspace."
user-invocable: false
argument-hint: '[request]'
---

# NW-NEW

Ask only enough to identify the requested outcome and whether evidence already
exists. Read durable product and design authorities before proposing work.

Route to the earliest missing owner:

- uncertain problem or user need -> `/nw-discover`;
- several plausible directions -> `/nw-diverge`;
- unclear job, journey or outcome -> `/nw-discuss`;
- unclear architecture, reuse or boundary -> `/nw-design`;
- unclear deployment/recovery constraint -> `/nw-devops`;
- stable product and design facts but no executable delivery contract ->
  `/nw-distill`.

Do not create, archive or resume a feature directory. Do not derive completion
from filesystem naming. DISTILL creates the immutable `DeliveryContract`; its
terminal result makes the later `/nw-deliver` invocation discoverable.
