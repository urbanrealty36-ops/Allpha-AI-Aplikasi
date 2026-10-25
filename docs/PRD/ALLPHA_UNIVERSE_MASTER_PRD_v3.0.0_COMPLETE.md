# ALLPHA UNIVERSE

# MASTER PRD v3.1 --- CONSOLIDATED PRODUCT, ENGINEERING, DESIGN SYSTEM & DELIVERY SPECIFICATION

**Document ID:** ALLPHA-MPRD-003\
**Version:** 3.1.0 --- v3.0.0 baseline preserved with AI Social Network, Creator Economy & AI Cinema addendum\
**Date:** 13 October 2026\
**Status:** Consolidated expanded product and engineering specification; see the v3.1 addendum for added Social Network and AI Cinema requirements\
**Primary product language:** Bahasa Indonesia\
**Secondary product language:** English\
**Product category:** AI Social Universe / AI Living World /
Human--Agent Social, Creative, Productive and Spatial Platform

> **Purpose of this document:** This is the single product direction and
> engineering reference for AI coding agents, product/design teams,
> backend engineers, mobile/web engineers, spatial/3D engineers,
> security engineers, QA and operations. It defines not only what Allpha
> contains, but how each system behaves, what data it owns, how it
> integrates, what must be tested, and what evidence is required before
> a feature can be called complete.

------------------------------------------------------------------------

# PART I --- DOCUMENT CONTROL AND PRODUCT CONTRACT

## 1. How to use this Master PRD

This document is intended to be read before code generation or
implementation. An implementation agent must not infer a different
product direction from isolated feature descriptions. When a feature is
unclear, follow the domain ownership, security, lifecycle, API, data and
acceptance rules in this document. If a real architectural decision
remains open, create an Architecture Decision Record (ADR) and mark the
dependency blocked until the decision is approved.

### 1.1 Normative language

-   **MUST / WAJIB:** required for acceptance.
-   **MUST NOT / DILARANG:** prohibited.
-   **SHOULD / SEBAIKNYA:** expected unless an approved ADR records a
    reason not to.
-   **MAY / BOLEH:** optional or context-dependent.
-   **Phase complete:** implementation, UI, backend, data,
    authorization, integrations, observability, documentation and
    required tests are complete for that Phase.
-   **Integration verified:** the feature has been exercised against its
    actual configured dependencies; a mock-only test does not qualify.
-   **Production verified:** the deployed environment has passed the
    relevant release checks and operational evidence is available.

### 1.2 Hard constraints

1.  **Build Allpha from zero** across client applications, backend, API,
    data model, AI engines, spatial runtime, commerce, security and
    operations.
2.  **Do not include PWA as a target product or architecture
    component.** The target clients are a mobile application, a web
    application and a separate Super Admin application; any technical
    delivery mode must be explicitly approved and must not reintroduce
    PWA as product scope.
3.  **Do not depend on or link to an old repository, old endpoint, old
    schema, old deployment or old implementation.** This PRD is a
    standalone new-build specification. The new project's repositories,
    domains, credentials and environments must be established as part of
    project setup.
4.  Do not assume legacy database records, asset catalogs, APIs or code
    are valid for this build.
5.  No fake business data in integration, staging or production.
    Synthetic data is permitted only in isolated test fixtures and must
    be visibly test-only.
6.  The frontend must not bypass the backend for privileged business
    operations.
7.  No provider secrets, payment secrets, private credentials or
    service-role keys may be embedded in clients.
8.  Every expensive or long-running operation must be bounded by policy,
    budget, timeout, quota and cancellation/recovery rules.
9.  Every Phase must be a usable vertical slice. Do not defer the real
    UI, business logic, permission rules, lifecycle, integration or
    error handling to the final QA Phase.
10. Final QA is for cross-system validation, regression, debugging,
    load/security testing, operational hardening and release
    readiness---not for first implementation of missing engines.
11. A UI, table, endpoint, workflow graph, successful build or green CI
    run alone does not prove a feature is complete.
12. AI Agent autonomy is bounded by owner intent, permissions, policies,
    risk controls, approvals and usage budgets.
13. Private owner data is not automatically available to public Agent
    users, external Agents, public workflows or shared sessions.
14. One canonical engine owns the lifecycle and business truth for each
    domain. Do not create duplicate authorities.
15. Spatial scenes and Agent-generated scene definitions are declarative
    and schema-validated; AI-generated arbitrary code must not execute
    inside the renderer or privileged backend.
16. The system must be resumable after interrupted generation or
    execution. Durable state and checkpoints are part of the design, not
    a later optimization.

## 2. Product definition

**Allpha is an AI Social Universe for Humans and AI Agents.** It
combines a social network, AI Agent ecosystem, personal knowledge and
learning environment, visual automation platform, 3D living world,
real-time live experience, collaboration platform, marketplace and
creator economy.

Allpha is not merely: - a chatbot with profiles; - a conventional social
feed with AI-generated posts; - a 3D city without real social/business
functions; - an avatar viewer without a real Agent runtime; - a workflow
canvas that cannot reliably execute or resume; - a document uploader
that has no retrieval evaluation or privacy boundary; - a token/credit
counter without cost and ledger correctness.

The product is a connected system in which a Human can create an Agent,
set its identity and boundaries, teach it through permitted knowledge
and skills, evaluate its performance, publish selected capabilities, let
other users interact with it under explicit scope, receive eligible
rewards, participate in communities, publish content, enter spatial
worlds, attend or host Live Experiences, and buy/sell permitted goods or
digital experiences.

## 3. Product loop

The principal user loop is:

1.  Create account and establish Human identity.
2.  Create or configure an AI Agent.
3.  Set persona, ownership, capabilities, data scopes, tools, model
    preferences and budget.
4.  Add knowledge, skills, memory policies and workflows.
5.  Evaluate the Agent through test sets and AI Challenges.
6.  Publish only the Agent capabilities and knowledge the owner chooses
    to share.
7.  Discover content, Humans, Agents, communities, Worlds, Districts,
    Booths and Live Experiences.
8.  Ask, collaborate, create, learn, transact and attend events.
9.  Receive feedback and performance data.
10. Improve a new Agent version and publish it under controlled
    versioning.
11. If enrolled in a creator program, receive eligible rewards after
    usage verification and settlement.
12. Manage privacy, usage, permissions, credits and account data at any
    time.

## 4. Product success principles

-   Every main journey has a defined start, successful end, failure
    states and recovery route.
-   Users can understand whether they are talking to a Human or an AI
    Agent.
-   Users can inspect what an Agent is allowed to do.
-   Users can distinguish private memory from published knowledge.
-   Expensive actions disclose limits or estimated usage where
    appropriate.
-   Long-running work displays progress and can resume safely.
-   Live sessions remain controllable by a Human host/moderator.
-   3D experiences degrade gracefully on low-capability devices.
-   Monetization does not depend on hidden, unlimited AI costs.
-   Public content and Agent capabilities are governed by moderation and
    takedown controls.

------------------------------------------------------------------------

# PART II --- USERS, ROLES AND PRODUCT SURFACES

## 5. Personas

### 5.1 Human / Individual

Needs identity, profile, content, discovery, messaging, a personal
Agent, memory/knowledge controls, privacy, usage transparency and the
ability to enter the Universe.

### 5.2 Agent Owner / Agent Builder

Needs to create and version Agents, add knowledge, author
skills/workflows, configure model policy, evaluate performance, control
public capabilities and inspect usage.

### 5.3 Agent Consumer

Needs to find public Agents, understand their capabilities and
limitations, ask questions, provide permitted inputs, review sources
where relevant, and know whether an interaction consumes credits.

### 5.4 Creator

Needs to publish posts, capsules, videos, live sessions, stage
experiences, themes, 3D assets, educational materials and permitted paid
content; measure legitimate engagement and manage rewards.

### 5.5 Educator / Mentor / Interviewer

Needs documents and slide decks, structured sessions, controlled AI
explanations, questions, annotations, participant roles, replay policy
and evaluation.

### 5.6 Business / Tenant / Advertiser

Needs a Booth, listings, tenant information, media surfaces, campaign
scheduling, audience rules, billing, analytics and takedown/compliance
controls.

### 5.7 Community Moderator

Needs reports, moderation queues, member controls, content/Agent
enforcement, evidence, appeal handling and audit.

### 5.8 Enterprise Administrator

Needs organization membership, roles, budgets, provider policy, data
scopes, integrations, audit and access controls.

### 5.9 Super Admin / Operations

Needs global configuration, user/Agent governance, model/provider
health, asset catalog, billing operations, moderation, security events,
queue health, cost dashboards and emergency kill switches. Privileged
actions require explicit permissions and audit.

### 5.10 Developer / Integrator

Needs API documentation, scoped credentials, OAuth applications, webhook
registration, provider/tool integrations, quotas, usage and revocation.

## 6. Roles and authority model

Roles are not sufficient by themselves. Authorization must evaluate
actor, action, resource, ownership, tenant, context, data
classification, purpose, entitlement and risk.

-   **Anonymous visitor:** public data only.
-   **Authenticated Human:** self-owned data and public data permitted
    by policy.
-   **Agent Owner:** configuration of own Agent, memory policies, tools,
    publication and versioning.
-   **Agent Runtime:** service identity with only the permissions
    granted to the current Agent task.
-   **Agent Consumer:** public or explicitly shared capabilities; no
    owner-private access by default.
-   **Session participant:** only session resources and actions granted
    by the host/session policy.
-   **Moderator:** scoped moderation actions; no blanket access to
    private user memory.
-   **Tenant admin:** tenant-scoped configuration and data.
-   **Super Admin:** privileged operational access by permission,
    purpose and audit; not a universal bypass for privacy.
-   **Worker/service identity:** only the job-specific resource and
    scope assigned by the backend.

## 7. Client applications

### 7.1 Allpha Mobile App

Primary mobile experience for onboarding, identity, social feed, Agent
interaction, knowledge/skill management, AI Challenges, messaging,
notifications, live participation, basic Stage controls, Universe
navigation and 3D District exploration. The architecture must support
native camera, microphone, notifications, secure credential storage and
platform lifecycle behavior.

The mobile client must: - use typed API contracts; - keep secrets out of
the app package; - handle offline/poor network states explicitly; - show
job progress and resumable status; - request camera/mic/files
permissions only when needed; - show AI identity disclosure; - expose
privacy/Agent permission controls; - support adaptive 3D quality and a
non-3D fallback for core tasks.

### 7.2 Allpha Web App

Full experience for content, Agent management, documents, Skill Builder,
Workflow Studio, Creator Studio, Theme/World Builder, spatial
exploration, Live Stage, marketplace and account settings. Complex
workflow and world-authoring interfaces may be desktop-optimized while
remaining responsive.

### 7.3 Allpha Super Admin

Separate application with a distinct security boundary and privileged
API scopes. It manages operations, governance, moderation, catalogs,
provider configuration, usage, billing, asset lifecycle, risk and
observability.

### 7.4 Allpha Developer Console

API keys/OAuth apps, integrations, webhooks, supported tool registry,
model/provider connections, documentation, usage, quota, credential
rotation and revocation.

### 7.5 Client/backend contract

All clients call the same canonical backend domain contracts. Clients do
not make direct privileged writes to business tables. Storage
upload/download flows must be issued and authorized by backend rules.

------------------------------------------------------------------------

# PART III --- DESIGN SYSTEM AND UI/UX

## 8. Design vision

The Allpha visual language is **futuristic, cinematic, crystalline,
spatial, intelligent, premium and readable**. The Universe can feel
immersive, but utility workflows must remain fast and comprehensible.

Visual themes: - galaxy, stars, orbital rings and spatial navigation; -
luminous capsule/content objects; - futuristic city, glass/metal
structures, holographic displays and neon accents; - AI characters and
human avatars; - distinct visual identities for World, District, Booth
and Stage; - controlled motion and depth rather than constant
animation; - readable typography and accessibility over decorative
effects.

## 9. Visual modes

### 9.1 Universe / Immersive mode

Dark navy/space surfaces, restrained electric blue, cyan and violet,
spatial depth, luminous edges, cinematic backgrounds and contextual
motion. Use for Universe Home, Galaxy/World navigation, Districts,
Booths, AI Character preview and Live Stage.

### 9.2 Work / Reading mode

High readability, quiet surfaces, strong contrast and low visual
distraction. Use for documents, knowledge, chat, workflow configuration,
settings, billing and admin tasks. Light and dark variants must both be
supported where practical.

### 9.3 Admin / Operations mode

Dense but readable layouts, clear status labels, tables, filters, audit
trails, charts and explicit confirmation for risky actions. Avoid
unnecessary 3D in operational screens.

## 10. Design tokens

Token values must be centralized and versioned. Do not scatter raw
color/spacing values throughout the client code.

### 10.1 Color roles

-   `brand.primary`: electric blue.
-   `brand.secondary`: violet.
-   `brand.accent`: cyan.
-   `brand.energy`: limited magenta for selected event/energy cues.
-   `surface.universe`: deep navy.
-   `surface.elevated`: blue-gray.
-   `surface.reading`: neutral light surface.
-   `surface.overlay`: translucent dark/light overlay with contrast
    safeguards.
-   `text.primary`, `text.secondary`, `text.muted`, `text.inverse`.
-   `status.success`, `status.warning`, `status.danger`, `status.info`.
-   `border.subtle`, `border.strong`, `focus.ring`,
    `selection.background`.
-   `spatial.glow`, `spatial.hologram`, `spatial.portal`.

Do not rely on color alone to indicate status. Status includes text/icon
labels.

### 10.2 Typography

-   Display font: modern geometric sans-serif for hero headings and
    Universe labels.
-   UI/body font: readable sans-serif with robust Latin and Bahasa
    Indonesia coverage.
-   Monospace/numeric font for IDs, code, tokens, costs and diagnostics.
-   Define tokens for font family, size, weight, line height, letter
    spacing and maximum line length.
-   Respect OS font scaling and user accessibility settings.

### 10.3 Spacing and layout

-   Base scale in 4 px increments.
-   Compact density for admin tables and workflow node editors.
-   Comfortable density for mobile interaction.
-   Larger spacing for immersive onboarding and stage controls.
-   Standard content max widths, grid breakpoints, safe areas and touch
    targets.
-   Avoid placing critical controls at inaccessible screen edges.

### 10.4 Shape and elevation

-   Consistent radii for small controls, cards, dialogs and immersive
    panels.
-   Use glow only for active/focused/spatially important elements.
-   Shadows convey layering, not decoration on every component.
-   Glassmorphism must not reduce contrast or text legibility.

### 10.5 Motion

-   Short transitions for controls and panels.
-   Meaningful transitions for portals, world changes and stage entry.
-   Interruptible animations and reduced-motion mode.
-   Avoid motion that delays user actions.
-   AI Character animation is driven by a formal animation contract, not
    arbitrary CSS or model-generated code.

## 11. Component library

Required shared components: - buttons: primary, secondary, tertiary,
destructive, loading, disabled; - text input, password/secret input,
search, textarea, select, segmented control; - form validation and
helper/error messages; - cards: Agent, content, Capsule, World,
District, Booth, Live, asset, workflow and listing; - modal, bottom
sheet, drawer and confirmation dialog; - tabs, breadcrumbs, bottom
navigation, sidebar and command/search palette; - data table with
sorting/filtering/pagination; - status chip and lifecycle timeline; -
upload dropzone, progress, validation result and retry; - job/task
progress and checkpoint state; - source citation and document
reference; - AI response, streaming response, tool trace and error
recovery; - Agent avatar/status/permission summary; - workflow node,
edge, port, branch and execution trace; - document/slide viewer with
page navigation and annotations; - live media tile, camera/mic control,
participant list, speaker queue and reconnect banner; - 3D canvas
controls, minimap, travel/teleport, quality settings and fallback; -
notification, toast, empty state, loading skeleton and error boundary; -
credit balance, quota, usage estimate and ledger entry; - audit event
and privileged action confirmation.

Every interactive control must have loading, success, empty, disabled
and failure behavior where applicable. Buttons must not be decorative
placeholders.

## 12. Information architecture and screens

### 12.1 Global navigation

Mobile primary navigation: **Home, Explore, Create, Messages, My
Agent**. Live, Universe and notifications must remain easy to discover
through contextual entry points and global actions.

Web navigation may use a sidebar, global search, creation entry point
and user/Agent switcher. Super Admin uses a separate admin navigation
and never reuses user-facing privileges implicitly.

### 12.2 Screen inventory

1.  Splash and onboarding.
2.  Account registration/login/recovery.
3.  Human profile and identity.
4.  Privacy, session and security settings.
5.  Universe Home.
6.  Galaxy/Universe Navigator.
7.  World Explorer.
8.  District 3D.
9.  Zone and Booth.
10. Agent profile and passport.
11. Feed and Moments.
12. Reels/video discovery.
13. Stories.
14. Content Capsule.
15. Ask/AI interaction.
16. Create Studio.
17. Agent Factory.
18. My Agent overview.
19. Agent permission center.
20. Memory & Knowledge Studio.
21. Skill Builder.
22. Workflow Studio.
23. AI Challenge & evaluation.
24. Agent version history/performance.
25. Live lobby and session creation.
26. Live Stage 3D.
27. Document/slide viewer.
28. AI Character preview/control.
29. Community.
30. Messaging/DM.
31. Search and Explore.
32. Marketplace.
33. Commerce, Credits and Billing.
34. Creator Studio/reward dashboard.
35. Theme/World Builder.
36. Asset Library and validation status.
37. Universe Map.
38. Notifications/activity.
39. Human Control Center.
40. Developer Console.
41. Super Admin Control Plane.
42. Operations/observability dashboards.

### 12.3 Essential UX flows

**Create and publish Agent** 1. User creates Agent. 2. Sets persona and
disclosure. 3. Chooses model policy and budget. 4. Sets tool and memory
permissions. 5. Adds knowledge/skills. 6. Runs tests. 7. Reviews privacy
and public capability summary. 8. Publishes selected version. 9.
Monitors use and can suspend/rollback.

**Use another person's Agent** 1. Consumer opens Agent Passport. 2. Sees
capabilities, data-use disclosure, usage cost/limit and owner-published
terms. 3. Starts session. 4. Backend binds request to consumer identity
and published Agent version. 5. Retrieval uses only public/explicitly
shared scope. 6. Usage is metered. 7. Consumer can report output; owner
can revoke capability.

**Build and resume workflow** 1. Create workflow. 2. Add nodes and typed
connections. 3. Validate schemas, permissions, budget and cycles. 4. Run
test execution. 5. Publish immutable version. 6. Monitor execution. 7.
If interrupted, inspect checkpoint and resume safely. 8. Inspect partial
outputs and failure cause.

**Live AI presentation** 1. Create session and select Stage. 2.
Upload/attach slides. 3. Set document audience and AI access. 4. Invite
participants and set roles. 5. Join media session. 6. Start AI
presentation. 7. Synchronize slide state, voice, animation and
annotations. 8. Pause, interrupt, change presenter or stop. 9. End
session and settle usage.

**District publishing** 1. Create content or ad campaign. 2. Validate
ownership/license and format. 3. Moderate. 4. Choose eligible media
surfaces and schedule. 5. Approve budget and targeting. 6. Publish
manifest. 7. Renderer displays authorized content. 8. Metrics and
takedown controls remain available.

------------------------------------------------------------------------

# PART IV --- DOMAIN AND ENGINE MAP

## 13. Domain ownership rule

The product has 82 capability domains, but these are not 82 independent
microservices or competing engines. Related domains must use shared
canonical engines. Each domain needs an owner, schema/API boundary,
lifecycle, permission policy, events, observability and tests.

## 14. Master inventory of 82 domains

### A. Human Identity, Agent & Intelligence

**1. Human Identity**\
Owns account profile, user preferences, locale, consent, account
lifecycle, privacy controls and user settings. It does not own Agent
runtime state or billing settlement.

**2. AI Agent Identity**\
Owns Agent identity, owner link, visibility, status, versions and public
profile. Every Agent must have an explicit owner or declared platform
ownership.

**3. Agent Persona**\
Owns tone, behavior profile, objectives, communication style, disclosure
and boundaries. Persona does not grant new tools or permissions.

**4. Agent Memory**\
Owns memory lifecycle, memory scope, retention, provenance, write
policy, retrieval policy and deletion.

**5. Agent Skills**\
Owns reusable skill definitions, schemas, versioning, tests, tool
dependencies and skill publication.

**6. Agent Capability**\
Declares actions/tools an Agent can request. Runtime policy still
authorizes every action at execution time.

**7. Agent Passport**\
Publishes owner-approved identity, verified capability claims, skill
versions, disclosures, reputation signals and usage terms.

**8. Interest Ontology**\
Defines normalized interests, topics, categories and semantic
relationships.

**9. Interest Graph**\
Represents permitted user/Agent relationships to interests, with
preference controls.

**10. Passion Graph**\
Represents deeper creator/topic affinity without inferring sensitive
traits unnecessarily.

**11. Habit Graph**\
Represents approved interaction patterns used for personalization; user
can inspect/control relevant data.

**12. Goal Graph**\
Tracks user/Agent goals, milestones, dependencies and progress.

**13. Context Graph**\
Represents task/session context with scope, provenance, expiry and
access policy.

**14. Social Graph**\
Owns follow, block, connection and visibility relationships.

**15. Relationship Graph**\
Models Human--Agent, Agent--Agent and account relationships with
explicit permissions.

**16. Community Graph**\
Models membership and relationships between community, member, role and
content.

**17. Content Graph**\
Models authorship, media, topics, replies, references and engagement
links.

**18. Knowledge Graph**\
Models entities, facts, relationships, sources, provenance and
confidence.

**19. Reputation Graph**\
Combines validated signals from use, quality, safety and participation.
Must resist sybil manipulation and not be treated as proof of truth.

### B. Content, Discovery & Social Interaction

**20. Agent Discovery**\
Searches public Agents by skill, category, capability, version,
availability and policy-safe quality signals.

**21. Content Ingestion**\
Validates, parses, moderates, indexes and versions uploaded content.

**22. Feed Engine**\
Builds paginated feed results from eligible content and ranking signals.

**23. Reels Engine**\
Handles short video metadata, processing, playback, captions, visibility
and recommendations.

**24. Stories Engine**\
Handles temporary content, audience scope, expiration and deletion.

**25. Live Engine**\
Owns live session lifecycle, roles, participant state and session-level
authorization.

**26. AI Live Engine**\
Connects Agent runtime, voice, permitted tools, presentation and
character animation to an authorized Live Session.

**27. AI Capsule Engine**\
Creates structured capsules from content/knowledge with source
references, visibility and versioning.

**28. Recommendation Engine**\
Ranks eligible content/Agent/world results using relevance, diversity,
safety and user controls.

**29. Personalization Engine**\
Adapts feeds, suggestions and navigation from allowed signals; must
support reset/disable controls.

**30. Search / Explore Engine**\
Provides cross-domain search for users, Agents, content, knowledge,
communities, Worlds, Districts, Booths, Live sessions and listings.

**31. Trend Engine**\
Detects emerging topics from valid signals and applies spam/manipulation
defenses.

**32. Social Interaction**\
Handles reactions, comments, mentions, shares, saves, reports and
interaction permissions.

**33. Messaging / DM**\
Owns conversations, participants, message state, attachments,
delivery/read state, block behavior and retention.

**34. Community Engine**\
Owns community creation, membership, roles, moderation, community
content and community events.

### C. Collaboration, Marketplace & Economy

**35. Collaboration Engine**\
Provides shared spaces, co-editing, annotations, comments, presence and
access control.

**36. Mission Engine**\
Defines objectives, tasks, milestones, verification rules and reward
hooks.

**37. Agent Catalog**\
Lists public Agent versions, capability declarations, terms,
price/entitlement and owner details.

**38. Marketplace**\
Owns listings, discovery, purchase rights, listing state and marketplace
policies.

**39. Commerce Engine**\
Owns orders, payment references, refunds, settlement state and
transaction integrity.

**40. Economy**\
Owns AI Credits, quota units, promotional credits and permitted
balance/ledger operations.

**41. Creator Economy**\
Owns eligible creator usage, revenue/reward calculations,
pending/settled balances, reversals and reports.

**42. Event Engine**\
Owns event schedule, registration, attendance, event-linked sessions and
lifecycle.

### D. Universe, Spatial Runtime & 3D World

**43. Agent World**\
Defines permitted Agent presence, movement, spawn points and interaction
scope within a World.

**44. Universe Engine**\
Owns Universe/Galaxy topology, world registry, navigation and spatial
hierarchy.

**45. District Engine**\
Owns District, zones, streets, roads, landmarks, buildings, plazas,
scene geometry references and spatial rules.

**46. Booth / Tenant Engine**\
Owns Booth identity, placement, tenant, catalog, interactions and
access.

**47. Tenant Leasing & Billing**\
Owns lease term, tenant entitlements, billing schedule, renewals, expiry
and termination.

**48. World / Scene Schema**\
Defines validated declarative scene data and schema compatibility.

**49. Theme Engine**\
Owns theme definitions, versions, visual variants and publishing
lifecycle.

**50. World Builder**\
Provides authoring, preview, validation, version comparison, publication
and rollback.

**51. Theme Marketplace**\
Owns theme listings, licensing, entitlements, versions and purchases.

**52. Agent Simulation Engine**\
Runs bounded behavior/simulation for characters and Agent presence;
simulation does not bypass permissions.

**53. Encounter Engine**\
Handles proximity, interaction invitations, encounter eligibility and
anti-spam controls.

**54. Presence Engine**\
Tracks online/session/spatial presence with expiry and privacy controls.

**55. Realtime World Engine**\
Synchronizes positions and world interactions that must be visible to
multiple clients.

**56. World Stream**\
Loads scene chunks, assets and state progressively according to
device/network budgets.

### E. Notifications, Governance, Security & Trust

**57. Notification Engine**\
Routes in-app/push/email notifications, preferences, deduplication and
delivery status.

**58. Analytics**\
Provides product and business metrics with privacy-safe aggregation and
access controls.

**59. Policy Engine**\
Evaluates rules for actions, data release, provider usage and
publication.

**60. Permission Engine**\
Authorizes actor/action/resource/context and returns allow/deny plus
reason codes safe for the caller.

**61. Risk Engine**\
Scores risk signals and invokes throttling, step-up, review or denial.

**62. Human Approval Engine**\
Manages approvals for sensitive tools, publication, sharing, external
effects and high-cost work.

**63. Audit Ledger**\
Records sensitive actions and financial/governance events with integrity
and retention rules.

**64. Trust & Safety**\
Handles reports, abuse, enforcement, appeals and incident workflows.

**65. Moderation**\
Moderates text, images, videos, documents, Agent profiles, skills,
listings, ads and Live content.

**66. Privacy**\
Owns consent, purpose, data export, deletion, retention, visibility and
provider-processing disclosures.

**67. Security**\
Owns secure architecture, authentication, authorization, secrets,
isolation, threat modeling and incident response.

**68. Identity Verification**\
Manages verification requirements and evidence when a feature/risk level
requires it.

**69. Anti-Impersonation**\
Detects misleading identity claims and supports
report/review/enforcement.

**70. Anti-Fraud**\
Detects abuse in payments, credits, rewards, marketplace and usage
patterns.

### F. Platform Control Plane & Developer Infrastructure

**71. Agent Interoperability**\
Allows controlled Agent-to-Agent exchange using explicit protocols, data
scopes and permissions.

**72. Agent API / Protocol**\
Provides versioned API/tool contracts, authentication, quotas, error
schemas and compatibility rules.

**73. Subscription / Billing**\
Owns plans, invoices, renewal, expiry, cancellation, refund and payment
reconciliation.

**74. Revenue Engine**\
Owns pricing/revenue attribution, platform fees, margin reporting and
eligible revenue rules.

**75. Entitlement Engine**\
Calculates server-side rights from plan, purchase, policy, role and
usage limits.

**76. Feature Flag Engine**\
Controls rollout, experiments and emergency kill switches with audit.

**77. Configuration Engine**\
Owns validated global, tenant and feature configuration with versioning.

**78. Super Admin Control Plane**\
Provides privileged operations across users, Agent catalog, moderation,
billing, assets, configuration and incident response.

**79. Developer Platform**\
Owns API applications, OAuth, credentials, webhooks, integrations,
developer documentation and usage.

**80. Observability**\
Owns logs, metrics, traces, alerts, SLOs and operational diagnostics.

**81. Evaluation Engine**\
Evaluates models, Agents, retrieval, workflow, privacy, animation and
safety.

**82. E2E Test / QA Engine**\
Runs repeatable cross-domain scenarios, regression, device/network
matrix and evidence collection.

------------------------------------------------------------------------

# PART V --- BACKEND AND PLATFORM ENGINES

## 15. Backend modularity

The backend must be organized by bounded domain modules, not one giant
file and not an unnecessary network of tiny services. Begin with a
modular backend and separate workers/processes where isolation, scaling,
resource profile or operational needs justify it. Service boundaries
must be explicit and documented.

Every domain module should define: - API routes and schemas; -
application/service logic; - data access/repository layer; -
authorization requirements; - domain events; - idempotency and
transaction behavior; - worker jobs if applicable; - error taxonomy; -
metrics/logs/traces; - migrations; - unit/integration/contract tests; -
user-facing and admin-facing UI dependencies.

## 16. API Gateway and request boundary

Every request must: 1. authenticate the caller where required; 2.
validate schema and payload size; 3. resolve tenant, owner and resource
context from trusted server state; 4. authorize the action; 5. apply
rate/concurrency limits; 6. reserve cost/budget if relevant; 7. invoke
domain logic; 8. persist transaction/state; 9. emit reliable events if
required; 10. return a stable response/error with request ID.

Do not trust `owner_id`, `tenant_id`, `role`, `price`, `credit_balance`,
`payment_status`, `published=true` or similar authority-bearing fields
simply because a client supplied them.

## 17. Identity, Authorization and Ownership Engine

### 17.1 Authorization input

-   actor identity and type;
-   requested action;
-   resource ID and resource owner;
-   tenant/org membership;
-   role and explicit permissions;
-   resource visibility/classification;
-   session context;
-   purpose/consent;
-   entitlement and quota;
-   risk level and approval state.

### 17.2 Decisions

Allow, deny, require step-up, require approval, limit scope, or defer
for review. Denials must be safe and must not leak whether a private
resource exists.

### 17.3 Ownership

Agent, private memory, private documents, credentials, workflow secrets
and personal settings must have explicit ownership. Public Agent
publication does not transfer ownership of private memory, private
source files or private tools.

## 18. Event, Queue and Worker Engine

Use durable jobs for tasks that outlive a normal API request: - document
parsing/indexing; - embeddings and reindexing; - Agent task execution; -
workflow runs; - 3D asset validation/conversion; - video/image
processing; - Live recording/transcoding; - scheduled ads/events; -
reward settlement/reconciliation; - exports/deletions; - evaluation
runs.

A job must include trusted owner/tenant context, job type/version,
resource references, idempotency key, retry policy, lease/heartbeat,
budget reference, trace ID and safe status. Workers must be isolated by
workload type when CPU/GPU/network permissions differ.

------------------------------------------------------------------------

# PART VI --- AI GATEWAY, MODEL ROUTER AND COST CONTROL

## 19. AI Gateway

The AI Gateway is the only approved route from product services to
model/provider execution. It handles policy, provider adapters, usage,
budgets, privacy, timeouts, retries, fallback and telemetry.

### 19.1 Supported capability classes

-   text generation and structured output;
-   embeddings;
-   reranking;
-   image understanding;
-   speech-to-text;
-   text-to-speech;
-   realtime voice/audio;
-   supported image/video generation;
-   supported 3D asset generation or external generation integration;
-   moderation/classification/evaluation.

Capability support is registered per provider/model and must be verified
by contract tests. Do not assume one model supports every capability.

## 20. Model Router

### 20.1 Routing inputs

-   task category and required capabilities;
-   quality tier and latency target;
-   plan/entitlement;
-   available user/tenant budget;
-   data sensitivity and provider policy;
-   context window and output limits;
-   provider health and capacity;
-   language and modality;
-   cache eligibility;
-   explicit user/owner provider preference.

### 20.2 Routing process

1.  Validate task and caller.
2.  Classify data sensitivity.
3.  Check entitlement and budget.
4.  Filter provider/model candidates by allowed capabilities and data
    policy.
5.  Estimate cost/latency.
6.  Choose an eligible candidate using routing policy.
7.  Reserve budget.
8.  Execute with bounded timeout/retry.
9.  Record actual usage and result metadata.
10. Apply fallback only to eligible failures and within budget.
11. Release unused reservation and settle actual usage.
12. Emit trace and usage event.

### 20.3 Fallback and circuit breaker

-   Retry only transient errors and within a configured limit.
-   Do not retry invalid requests, policy denials or non-idempotent
    effects blindly.
-   Use circuit breakers for unhealthy providers.
-   Preserve request correlation and idempotency.
-   Do not silently downgrade a task when quality or privacy
    requirements would be violated.
-   Report partial success and fallback in a user-appropriate way.

## 21. Global LLM infrastructure and Free/Paid routing
Free usage may be routed to eligible open/self-hosted model
infrastructure where licensing, hardware capacity, safety, latency and
total cost allow. Paid tiers may receive access to additional
models/providers or higher-quality capabilities according to policy. The
PRD intentionally defines routing behavior generically;
provider-specific selections and pricing belong in a versioned provider
registry and approved ADR.

The cost of self-hosting is not zero: GPU capacity, power, server/cloud,
storage, bandwidth, monitoring, security and operations must be counted.

## 22. Cost-saving controls

-   Prefer deterministic code/templates for deterministic tasks.
-   Use small/cheap models for classification, routing, extraction and
    simple summaries.
-   Escalate to stronger models only when task policy requires it.
-   Bound input/output tokens and context size.
-   Summarize long history and retrieve only relevant chunks.
-   Use cache only within matching user/tenant/permission scope.
-   Deduplicate embedding jobs.
-   Batch eligible background work.
-   Cap Agent loops, node calls, tool calls, retries, parallel tasks and
    runtime.
-   Use admission control and budget reservation for expensive work.
-   Separate inference, embeddings, voice, media, storage, GPU and 3D
    costs.
-   Provide budget alerts and per-Agent/workflow/user dashboards.
-   Stop or pause jobs when quota is exhausted, with a clear recovery
    path.
-   Never promise unlimited high-cost capabilities on a fixed low price
    without measured unit economics.

## 23. BYO model/API connection

Users may connect a supported personal provider or model endpoint
through a controlled adapter.

Required workflow: 1. Select provider type and supported capability. 2.
Enter credential into a secure server-mediated form. 3. Encrypt/store
secret in vault; return only a masked identifier. 4. Validate endpoint
allowlist and block private/internal network destinations. 5. Test
connection and capability with a bounded safe request. 6. Define allowed
Agent/tenant scope and budget. 7. Route calls through the same AI
Gateway and metering. 8. Allow credential rotation/revocation. 9. Log
metadata but not raw secret or sensitive payload by default.

A BYO provider must not bypass safety, authorization, privacy
classification, cost limits or audit. Users must be informed about
provider processing and data handling.

------------------------------------------------------------------------

# PART VII --- AGENT RUNTIME, ORCHESTRATION AND RESUMABILITY

## 24. Agent Runtime

An Agent is a versioned policy-bound identity that can reason through a
task, retrieve permitted context, request tools, execute skills and
return a result. The model itself is not the authority. Runtime policy
decides what the Agent may do.

### 24.1 Agent task lifecycle

`created → queued → policy_check → budget_reserved → context_building → planning → executing → validating → succeeded`

Alternate states: `waiting_for_approval`, `waiting_for_input`,
`retrying`, `partially_succeeded`, `failed`, `cancelled`, `timed_out`,
`budget_exhausted`.

### 24.2 Task envelope

-   task ID and version;
-   requester and Agent IDs;
-   Agent version pinned at start;
-   owner/tenant context;
-   input reference and classification;
-   allowed memory/knowledge scope;
-   allowed tools and capability scope;
-   budget/quota reservation;
-   deadline and cancellation state;
-   workflow/trace correlation;
-   output references and safe error information.

### 24.3 Tool execution

-   Tools have strict input/output schemas.
-   Tool calls are authorized outside model output.
-   High-risk tools require approval.
-   Network and filesystem access are allowlisted and sandboxed.
-   Tool output is untrusted data.
-   Side effects use idempotency keys where possible.
-   Tool results are size-limited, sanitized and classified before being
    added to context.

## 25. Orchestration Engine

Capabilities: - single-Agent execution; - specialist delegation under
explicit scopes; - task DAG and dependencies; - bounded parallel
execution; - conditional branches; - loops with maximum iterations and
budget; - human approval/wait states; - retries, cancellation, timeout
and compensation; - durable checkpointing; - event-triggered
execution; - progress streaming; - trace and cost aggregation.

Orchestration must not become a second hidden workflow engine. It
coordinates Agent tasks and delegates durable graph execution to the
canonical Workflow Engine where appropriate.

## 26. n8n-like Visual Workflow Engine

### 26.1 Node families

**Triggers:** manual, schedule, webhook, domain event, approved external
event.\
**AI:** model call, Agent task, classifier, extractor, summarizer,
evaluator.\
**Memory:** retrieve, propose write, summarize, source reference.\
**Knowledge:** ingest, index status, search, retrieve, cite.\
**Control:** if/else, switch, bounded loop, parallel, join, wait,
approval, subworkflow.\
**Integration:** supported API connector, HTTP to approved domains,
approved database action, webhook.\
**Content:** draft, transform, moderate, request publication.\
**Live:** session event, authorized slide action, approved character
intent.\
**Economy:** estimate cost, check quota, request eligible reward
evaluation.\
**Utility:** map fields, validate, deduplicate, schedule, notify.

### 26.2 Node contract

Each node defines: - stable node type/version; - input/output JSON
schema; - permission scope; - side-effect classification; - retry and
timeout; - idempotency policy; - cost estimate/class; - output
retention; - safe logging rules; - compatibility/migration rules; - test
cases.

### 26.3 Workflow authoring UX

-   canvas with typed ports and edges;
-   zoom/pan/minimap;
-   node search and category palette;
-   schema-driven node configuration;
-   inline validation and error locations;
-   test with explicit test inputs;
-   cost/permission preview;
-   draft and immutable published versions;
-   run history, trace, per-node input/output references;
-   retry/resume/cancel controls;
-   credentials referenced by vault ID, never embedded in workflow
    export;
-   import/export with schema validation and no secret export.

### 26.4 Durable execution and resume

Every run records execution ID, immutable workflow version,
owner/tenant, trigger, current node, attempts, state version,
checkpoints, budget, events and error details.

**Required behavior** 1. Persist a node's validated result before
advancing to dependent nodes. 2. Use a worker lease/heartbeat so
abandoned executions can be detected. 3. On worker failure, recover from
the latest durable checkpoint. 4. Retry only according to the node's
retry policy. 5. Use idempotency keys for external effects. 6. Before
replaying an uncertain side effect, query the external system when
supported. 7. Never re-run completed safe nodes simply because a later
node failed. 8. Preserve partial output and clearly mark it partial. 9.
Permit cancel, retry-from-node, resume and replay-as-new-run. 10. Resume
only with a compatible workflow version and valid state; otherwise stop
safely and explain required intervention. 11. Do not store provider
secrets in checkpoint payloads or logs. 12. Record budget reserved,
spent and released. 13. Provide user-visible progress and
estimated/actual usage. 14. Apply retention/deletion to input/output
payloads and artifacts. 15. Use at-least-once job delivery with
idempotent processing where exactly-once effects cannot be guaranteed.

### 26.5 Interrupted generation

For AI content/3D generation: - persist job intent and normalized
parameters; - store provider/job identifiers where supported; - persist
each completed stage/artifact; - validate checksums and output
metadata; - resume at the last safe stage; - avoid duplicate provider
charges where provider idempotency/status lookup exists; - show partial
results and exact failure stage; - allow retry with modified parameters
as a new version; - preserve provenance and cost records.

------------------------------------------------------------------------

# PART VIII --- MEMORY, SEMANTIC MEMORY, HYBRID MEMORY AND RAG

## 27. Memory model

Memory is not a single vector table. It is a governed service for
different kinds of state and knowledge.

### 27.1 Working memory

Short-lived context for a live session or current task. It expires
according to session policy and should not become long-term memory
automatically.

### 27.2 Episodic memory

Summaries of events/interactions with timestamps, actors, provenance and
retention. Only eligible facts may be retained.

### 27.3 Semantic memory

Normalized facts, concepts and relations extracted from approved
sources. Must retain source references, confidence, version and scope.

### 27.4 Procedural memory

Reusable task patterns or instructions. It does not grant tool authority
and must pass skill/workflow validation before execution.

### 27.5 Long-term memory

Persistent items subject to user consent, retention, correction and
deletion controls.

### 27.6 Knowledge corpus

Documents, pages, approved API results, datasets and derived chunks.
Knowledge source and personal memory are different concepts and must be
separately permissioned.

### 27.7 Published knowledge

An owner-selected subset with explicit audience and purpose. Publishing
knowledge does not publish the original private file unless that access
is separately granted.

## 28. Hybrid retrieval architecture

Retrieval must combine semantic/vector search, keyword/full-text search
and metadata constraints. A query must never search every user's vector
corpus and attempt to hide unauthorized results after the fact.

Pipeline: 1. Authenticate caller and resolve Agent/session scope. 2.
Determine allowed namespaces and document visibility. 3. Classify
request and sensitive data. 4. Construct query using permitted context.
5. Run vector search with owner/tenant/Agent/visibility filters. 6. Run
keyword/full-text search with the same filters. 7. Merge and deduplicate
results. 8. Rerank within configured latency/cost. 9. Apply freshness,
trust, source quality and version rules. 10. Build a bounded context
window with citations/source IDs. 11. Generate through Model Router. 12.
Validate response/citations where required. 13. Store retrieval trace
metadata with sensitive-content minimization. 14. If configured, propose
memory write; Memory Policy decides whether to persist.

### 28.1 Retrieval quality

Track recall/precision, citation accuracy, answer relevance,
stale-source rate, retrieval latency and cost. Maintain evaluation sets
for Indonesian and English, different document formats and adversarial
instructions.

### 28.2 Memory write governance

The model can propose memory but cannot force a write. The engine
evaluates: - source reliability; - consent and purpose; -
classification/sensitivity; - owner and namespace; -
duplication/conflict; - confidence and provenance; - retention/expiry; -
user correction/deletion state; - whether the item belongs in memory or
should remain session-only.

### 28.3 Forgetting, deletion and correction

When a user deletes/revokes a source, the system must track downstream
chunks, embeddings, summaries, caches and derived indexes and
remove/restrict them according to policy. If a derived artifact cannot
be removed immediately, it must be marked inaccessible while deletion
propagates. Document this behavior transparently.

------------------------------------------------------------------------

# PART IX --- AGENT LEARNING, SKILLS AND AI CHALLENGE

## 29. Agent Development Studio

Each Agent has a studio with tabs: 1. Overview and public identity. 2.
Persona and instructions. 3. Knowledge sources. 4. Memory policies. 5.
Skills and tools. 6. Workflows. 7. Model/provider policy. 8. Privacy and
access scopes. 9. Evaluation and AI Challenge. 10. Version history. 11.
Performance/usage/cost. 12. Publication and reward settings.

## 30. Knowledge ingestion and upload

### 30.1 Initial format support

Required initial formats: PDF, Markdown, TXT and DOCX. PPTX, EPUB/ebook,
spreadsheets, images and additional formats may be enabled only after
parser quality, security and source mapping tests pass.

### 30.2 Pipeline

1.  Upload to a private quarantine location.
2.  Validate signature/MIME/size and reject unsupported or malformed
    files.
3.  Malware scan and safe parser selection.
4.  Verify ownership and upload permission.
5.  Parse in an isolated worker with CPU/memory/time limits.
6.  Extract text, page/slide boundaries, tables and metadata.
7.  Detect sensitive data and classify source.
8.  Split into chunks with source location and version.
9.  Generate embeddings via Model Router.
10. Index in vector and full-text search.
11. Run retrieval smoke/evaluation checks.
12. Mark `ready` only after required checks pass.
13. Provide progress, failure stage and retry.
14. Support source replacement, reindex and deletion propagation.

### 30.3 Source connectors

URL/API connectors must use allowlists, SSRF protection,
robots/terms/legal checks where applicable, scoped credentials, rate
limits, change detection and provenance. Do not crawl arbitrary internal
URLs.

## 31. Skills

A Skill is a versioned capability definition with: -
name/description/category; - inputs/outputs and schemas; - instructions
and constraints; - tool dependencies; - required permission scopes; -
model capability requirements; - budget/time limits; - tests and
evaluation rubric; - author/source/provenance; - version, changelog and
status; - publication/entitlement terms.

Skills do not directly grant permission. Runtime checks each
tool/action.

## 32. Learning methods and boundaries

-   Uploading a document adds retrievable knowledge; it does not
    automatically retrain model weights.
-   Memory stores eligible user/Agent information under consent and
    retention policy.
-   Skills define reusable procedures and constraints.
-   Workflows define executable, validated sequences.
-   Feedback may create a proposal for improvement but does not
    automatically rewrite a published Agent.
-   Fine-tuning is optional and only used when provider capability, data
    rights, cost, consent and measurable evaluation justify it.
-   Public Agent versions should pin skill versions, knowledge
    snapshot/index version, tool permissions and model policy.
-   Owner reviews and approves publication of material capability
    changes.

## 33. AI Challenge

Challenge lifecycle: 1. Choose category/objective. 2. Define task set,
expected behavior and rubric. 3. Select allowed knowledge, skills and
tools. 4. Run test suite in an isolated evaluation context. 5. Measure
correctness, relevance, task success, citations, safety, latency and
cost. 6. Run privacy and prompt-injection tests. 7. Compare against
previous Agent version. 8. Present evidence and tradeoffs to owner. 9.
Owner approves or rejects release. 10. Publish immutable version if
approved. 11. Monitor real use and feedback. 12. Roll back or suspend if
quality/safety regresses.

Challenge categories include document analysis, tutoring, language
learning, coding, research, business analysis, presentation,
interviewing, mentor support, content creation and workflow automation.

### 33.1 Challenge anti-cheat

-   use hidden/rotating evaluation cases where appropriate;
-   prevent test data leakage into training/knowledge;
-   rate-limit submissions;
-   detect repeated synthetic activity;
-   record evaluator version and test-set version;
-   separate public score from private sensitive data;
-   avoid rewarding raw volume over quality.

## 34. AI Credits Reward for Agent owners

Reward is not equivalent to raw token count. A reward event must be
eligible, successfully completed, policy-compliant and attributable.

Required ledgers: - user credit consumption; - actual inference/infra
cost; - creator pending reward; - creator settled reward; -
refund/reversal; - promotional credit and expiry.

Settlement flow: 1. Record usage event with unique ID. 2. Determine
whether service was successfully delivered. 3. Check requester/owner
relationship and anti-fraud rules. 4. Calculate eligible value from
approved program formula. 5. Record pending reward. 6. Apply
dispute/chargeback/risk delay if necessary. 7. Settle once using
idempotency key. 8. Reverse with a linked entry if required; do not
erase history. 9. Show owner an understandable usage/reward statement.

Exclude invalid, spam, duplicate, failed or prohibited activity.
Distinguish platform-only credits from cash payout. Any cash-out, tax or
financial treatment must be reviewed before launch and must not be
implied by the term "AI Credits".

------------------------------------------------------------------------

# PART X --- LIVE STREAMING, DOCUMENTS, STAGE 3D AND AI CHARACTER

## 35. Live Experience product definition

Live Experience is a realtime environment in which Humans and AI Agents
can present, teach, discuss, interview, pitch, analyze documents,
co-create and interact in a spatial Stage.

It is not complete until media transport, Stage state, document
pipeline, AI runtime, voice, animation, permissions, participant UX,
failure recovery and usage accounting work together.

## 36. Core Live entities

-   Stage template and version;
-   Live Session and lifecycle;
-   participant and role;
-   media publication/subscription;
-   camera/virtual camera slot;
-   Stage layout and scene reference;
-   document attachment and access grant;
-   presentation/slide state;
-   annotation/shared pointer;
-   AI Agent participant and Agent version;
-   voice generation/stream metadata;
-   animation intent and timeline;
-   chat/question/speaker queue;
-   recording metadata/consent/retention;
-   session budget and usage ledger;
-   moderation/risk events.

## 37. Live Session lifecycle

`draft → scheduled → lobby → live → paused → ending → ended`

Alternate outcomes: `cancelled`, `failed`, `terminated_by_moderation`.

Session state changes must be authorized and versioned. A participant
cannot change host-owned state simply by sending a client event.

## 38. Roles and permissions

-   **Host:** starts/ends session, manages layout, grants document
    access, delegates controls.
-   **Co-host:** limited delegated controls.
-   **Speaker:** may publish allowed media and use approved presentation
    controls.
-   **AI Agent:** has a declared role and constrained skills/tools.
-   **Audience:** views/interacts according to session settings.
-   **Moderator:** applies scoped safety controls.
-   **Observer/recorder:** only where explicitly allowed and disclosed.

Permission examples: publish camera, publish mic, share screen, view
document, control slides, annotate, speak, invite, remove participant,
invoke Agent, access recording, download attachment. These must be
separate permissions.

## 39. Human camera versus AI Character camera

These are distinct media/rendering sources.

### 39.1 Human media

-   device camera;
-   microphone;
-   screen share or permitted presentation share;
-   optional avatar/identity tile;
-   explicit OS permission and user consent;
-   media publication controlled by session permissions.

### 39.2 AI Character view

-   virtual camera/rendered view of a 3D avatar;
-   animation state and pose;
-   voice/audio stream;
-   facial/viseme timeline;
-   optional scene-relative placement;
-   explicit AI identity disclosure.

### 39.3 Stage layout

The layout engine composes independent slots: Human video tiles, AI
Character view, document/slide screen, shared screen, speaker tiles,
chat/annotations and Stage environment. A Stage may show Human + AI side
by side, AI presenter plus slides, panel/podcast, interview layout,
tutor board or avatar-only experience.

AI "camera" does not mean a physical camera attached to the AI. It is a
virtual viewpoint or rendered avatar feed. The Human camera must not be
silently activated by an AI Agent.

## 40. Media transport architecture

-   Backend authorizes session, participant roles and media actions.
-   Backend issues short-lived session/media credentials.
-   WebRTC signaling negotiates connections.
-   An SFU distributes media for multi-participant sessions.
-   STUN/TURN supports connectivity across networks.
-   Adaptive bitrate and reconnect logic handle network changes.
-   Recording/transcoding runs in isolated media workers and follows
    consent/retention.
-   Realtime events synchronize slide state, participant state,
    reactions and animation cues.
-   FastAPI does not proxy every media frame.
-   Media service failure must produce clear UI state and recovery path.

Specific SFU/TURN/recording providers are an ADR, not hard-coded product
logic.

## 41. Live Experience templates and modes

Required template families: - Podcast Studio; - Talkshow; -
Presentation; - Pitching Room; - News Stage; - Product Marketing; -
Classroom; - Mentor Room; - Tutor Room; - Interview Room; - Analysis
Room; - Collaboration Room; - Panel Discussion; - Workshop; - Community
Event.

Each template defines geometry/layout, participant slots, virtual
screens, allowed actions, default camera angles, lighting, media
surfaces, accessibility fallback and performance budget.

## 42. Document and presentation engine

### 42.1 Attachment types

PDF, PPTX, Markdown and supported document formats. Unsupported or
unsafe files must be rejected clearly.

### 42.2 Document states

`uploaded → quarantined → scanning → parsing → extracting → indexing/previewing → ready`

Alternate states: `rejected`, `failed`, `needs_review`, `revoked`,
`deleted`.

### 42.3 Presentation pipeline

1.  Host creates Live Session and selects Stage template.
2.  Host uploads or attaches a document.
3.  Backend validates type, size, ownership and permissions.
4.  File enters private/quarantine storage.
5.  Parser extracts page/slide structure, text, tables and permitted
    images.
6.  Preview renderer creates page/slide assets.
7.  Document engine creates source map (page, slide, section, element).
8.  Host configures audience access separately from AI access.
9.  Stage renderer displays slide/page on a virtual screen surface.
10. Presentation state tracks active slide/page, transition and
    annotations.
11. Realtime events synchronize the state to authorized participants.
12. AI retrieval receives only the allowed document scope and relevant
    sections.
13. AI generates an explanation/answer.
14. Voice runtime generates/streams audio when enabled.
15. Animation runtime synchronizes voice timestamps with visemes, gaze,
    expression and gestures.
16. Host can pause, interrupt, change slide, hand over to Human or stop
    AI.
17. Session end applies retention, recording and usage policies.

### 42.4 AI presentation behavior

The Agent can be assigned modes: - explain slides in order; - summarize
a document; - analyze and compare information; - answer audience
questions; - tutor a learner; - interview a candidate; - act as
mentor; - co-host a podcast/talkshow; - deliver a pitch; - present
product information.

Each mode defines a task prompt/template, allowed source scope, tool
permissions, audience disclosure, response style, turn-taking rules,
citation behavior and safety restrictions. The mode is configuration
over shared engines, not a new duplicated engine for every role.

### 42.5 Document privacy

-   Seeing a slide does not automatically grant download permission.
-   AI access and audience access are separate.
-   Private documents cannot be silently indexed into public knowledge.
-   Revocation blocks future access and triggers derivative cleanup
    according to policy.
-   External model processing follows data classification and provider
    policy.
-   Logs store references and diagnostic metadata, not full confidential
    documents by default.

## 43. Live collaboration

-   chat and Q&A;
-   speaker queue and host handoff;
-   shared pointers and annotations;
-   slide/page navigation by authorized users;
-   collaborative notes or documents where enabled;
-   participant presence and reactions;
-   role-based camera/mic controls;
-   co-host actions;
-   shared 3D objects/boards where supported;
-   session event history;
-   consent-controlled recording and replay.

Concurrent updates require a defined authority/merge policy. For
example, only host/co-host may control the global slide index unless
delegation is granted.

## 44. AI Character Animation Engine

### 44.1 Required animation channels

-   full-body skeletal movement;
-   locomotion: idle, walk, turn, run where asset supports it;
-   posture and upper-body gestures;
-   face expressions;
-   eyes, gaze direction and blink;
-   brows and facial controls;
-   mouth shapes/visemes for lip-sync;
-   hand gestures, pointing and object interaction;
-   inverse kinematics where supported;
-   animation transitions and blending;
-   emotion/intent cues bounded by policy;
-   voice/animation timestamps;
-   scene-relative movement and navigation.

### 44.2 Asset capability contract

Each character asset declares: - skeleton/rig identity and compatible
hierarchy; - supported animation clips and state names; - facial
blendshapes or equivalent controls; - viseme map; - eye/look-at/blink
support; - hand/gesture library; - IK capabilities; - root-motion
policy; - scale, bounds and coordinate conventions; - LOD and device
performance profile; - licensing/provenance; - fallback capabilities.

A static mesh cannot provide full body/face animation merely through
application code. Assets that lack required rig/blendshape support must
be marked with their actual capability and use an honest fallback.

### 44.3 Animation state layers

1.  locomotion/body;
2.  upper-body gesture;
3.  interaction/IK;
4.  facial expression;
5.  eye gaze/blink;
6.  lip-sync/viseme;
7.  safety/idle fallback.

Runtime resolves priority conflicts, blends transitions and prevents
impossible simultaneous states.

### 44.4 AI-to-animation contract

The Agent emits a constrained semantic intent, such as: -
`speak(text_or_audio_reference)`; - `expression=curious`; -
`gesture=point_to_slide`; - `gaze=audience`; - `interaction=wave`; -
`movement=walk_to_anchor`.

It does not emit arbitrary executable animation code. Animation Runtime
validates intent against asset capabilities, policy, current state and
Stage context.

### 44.5 Voice synchronization

-   Audio segments carry timestamps/sequence IDs.
-   Viseme/animation events align to audio timeline.
-   Reconnect or buffering must resynchronize state.
-   If voice stops, mouth animation returns to idle safely.
-   If the asset lacks visemes, use a disclosed/fallback animation
    rather than claiming accurate lip-sync.
-   Captions/transcripts should be available where supported.

### 44.6 Character movement in a District

Character pathfinding uses validated navigation geometry, collision,
movement bounds, spawn points and interaction anchors. Agent intent is
authorized by runtime; Spatial Engine executes only valid
movement/actions. Characters must not walk through blocked geometry or
interact with private Booth/session resources without permission.

## 45. Live acceptance criteria

-   Host can create, schedule, start, pause and end a session.
-   Human camera/mic permissions are explicit and can be revoked.
-   AI avatar and Human media occupy separate Stage slots.
-   PDF/slide content is visible to the intended audience and not to
    unauthorized users.
-   AI can explain a permitted slide/document and answer within allowed
    scope.
-   Slide state, voice and animation are synchronized within the defined
    quality target.
-   Host can interrupt/mute/stop AI.
-   Session recovers from participant reconnect and provider/media
    interruption.
-   Usage quota is enforced and recorded.
-   Session events and sensitive actions are audited.
-   Mobile devices can join with a usable fallback when 3D quality is
    limited.

------------------------------------------------------------------------

# PART XI --- SPATIAL ENGINE, DISTRICT AND 3D ASSETS

## 46. Spatial hierarchy

`Universe/Galaxy → World → District → Zone → Booth/POI → Scene Object / Media Surface`

Each level has stable identity, owner/governance, version, access
policy, spatial bounds and scene references. The hierarchy is
data-driven and validated. A World or District is not simply a single
giant GLB file; it is a structured scene with assets, state and
interaction contracts.

## 47. Universe Engine

-   registers Worlds and versions;
-   defines navigation links/portals;
-   controls public/private/entitled access;
-   provides search and discovery metadata;
-   tracks world entry/exit and relevant presence;
-   uses versioned scene references;
-   supports rollback/deprecation.

## 48. World and Scene Schema

Schema describes: - world identity/version; - coordinate system and
units; - environment/lighting references; - scene chunks; - navigation
and collision data; - object placements and interaction anchors; -
Booth/tenant/media surface references; - spawn points; - allowed
interactions; - asset references pinned to versions; - device quality
variants; - moderation/publication metadata.

The schema must be validated before publishing. User/Agent content
cannot inject executable code into the renderer.

## 49. District Engine

District contains: - roads, streets and sidewalks; - building blocks,
facades and rooftops; - landmarks, plazas and points of interest; -
Booths and tenant locations; - Live Experience locations; - billboards
and videotrons; - spawn/teleport points; - navigation mesh/pathfinding
data; - collision and interaction bounds; - spatial audio zones if
supported; - public/private/paid areas; - content discovery zones; -
world-streaming chunks and LOD.

### 49.1 Navigation

-   keyboard/controller/touch controls as appropriate;
-   camera modes (first-person, third-person, orbit) according to
    client;
-   pathfinding for AI Characters;
-   collision and walkable surfaces;
-   fast travel/portal only where allowed;
-   accessibility option for non-3D list/map navigation;
-   network-aware loading and recovery.

### 49.2 Spatial presence

Track only the state needed for presence and synchronization. Use
relevance filtering so clients do not receive every movement event for
every entity in the city. Position updates have rate limits, bounds
validation and anti-cheat checks.

## 50. Booth and Tenant Engine

A Booth includes: - stable Booth ID and placement; - tenant/owner; -
theme and scene version; - catalog/listings/services; - media
surfaces; - entry/access rules; - lease/entitlement; - interactions and
CTA; - analytics; - moderation and publication state.

Tenant leasing and billing are separate business lifecycle records, but
the Booth Engine remains the authority for the Booth itself.

## 51. Media Surface and Ads Engine

### 51.1 Surface types

-   building billboard;
-   digital videotron;
-   holographic panel;
-   Booth display;
-   event/Stage screen;
-   public announcement surface;
-   Creator content display;
-   sponsor surface.

### 51.2 Surface schema

-   surface ID and owner/tenant;
-   scene/world/district placement and transform;
-   aspect ratio, resolution and media capabilities;
-   campaign/content reference;
-   allowed content categories;
-   approval/publish status;
-   schedule and time zone;
-   targeting policy;
-   frequency cap;
-   budget/entitlement;
-   impression/click/view definitions;
-   moderation/takedown status;
-   performance/LOD requirements.

### 51.3 Ad delivery

1.  Advertiser/Creator submits campaign/content.
2.  Ownership, rights, format and policy are validated.
3.  Moderation/approval occurs.
4.  Campaign eligibility checks schedule, budget, audience, surface,
    frequency and policy.
5.  Ads Engine returns an authorized manifest.
6.  Spatial renderer displays the content.
7.  Valid view/impression/click events are recorded with deduplication
    and fraud controls.
8.  Campaign can be paused, ended or removed.
9.  Billing and analytics reconcile against defined metrics.

Renderer does not decide business eligibility and cannot publish
unapproved content.

## 52. AI Character in the city

-   character identity and Agent version;
-   allowed movement zone;
-   navigation path;
-   behavior state;
-   interaction anchors;
-   visibility and presence policy;
-   conversation invitation rules;
-   voice/animation state;
-   resource/CPU/GPU budget;
-   interaction history according to privacy policy.

The simulation system must not run an unlimited Agent loop for every
visible character. Use bounded state machines, event-triggered
reasoning, relevance thresholds and budgeted interaction.

## 53. Fourteen 3D asset categories

The taxonomy below is the proposed canonical taxonomy for the new build
and must be locked against the asset schema before implementation.

1.  **Universe & Galaxy:** cosmic environment, planets, orbits, galaxies
    and navigation elements.
2.  **World & Environment:** terrain, sky, landscape, atmosphere and
    world background.
3.  **District & Landmark:** city blocks, streets, buildings, towers,
    plazas and landmarks.
4.  **Booth & Tenant:** shops, kiosks, pavilions, business interiors and
    tenant structures.
5.  **Live Experience Stage:** podcast, talkshow, presentation,
    pitching, classroom, tutor, mentor, interview and event stages.
6.  **AI Character & Animation:** rigged Agents, skeletal animations,
    facial rigs, visemes and gestures.
7.  **Human Avatar & Uniform:** human avatar bases,
    formal/casual/hero/Nusantara-style uniforms and compatible
    accessories, subject to licensing.
8.  **Portal & Navigation:** portals, gates, teleport anchors, beacons
    and wayfinding objects.
9.  **Spatial FX & Visual Effects:** particles, aura, trails, energy,
    transitions and ambient effects.
10. **Interior & Furniture:** chairs, tables, desks, lights, room
    layouts and props.
11. **UI Props & Holograms:** floating panels, holographic interfaces,
    display frames and spatial UI props.
12. **Interactive Objects:** doors, buttons, presentation pointers,
    objects that can be selected or used.
13. **Collectibles & Rewards:** badges, trophies, crystals, reward
    objects and permitted digital collectibles.
14. **Materials, Lighting & Theme FX:** materials, shaders, lighting
    profiles, post-processing and theme atmosphere.

### 53.1 Asset metadata

Each asset requires: - stable ID and category; - version and hash; -
owner/source/provenance; - license and allowed usage; - file format and
size; - dimensions/bounds/scale; - texture/material metadata; -
rig/animation capabilities if relevant; - LOD variants; - compatibility
requirements; - validation/moderation status; - publication status; -
storage object reference; - public/private access policy; - renderer
manifest reference.

### 53.2 Asset lifecycle

`draft → uploaded/quarantined → validating → review → approved → published → deprecated/retired`

Alternate statuses: `rejected`, `failed`, `blocked`, `revoked`. Only
approved/published assets may be exposed through public manifests.
Publication requires file validation, licensing/provenance review,
security scan, moderation, performance budget and compatibility checks.

### 53.3 Renderer and performance

-   asset chunking and lazy loading;
-   LOD and texture variants;
-   frustum/occlusion culling where supported;
-   instancing/batching;
-   bounds and collision validation;
-   device capability profiles;
-   low-power mode;
-   2D/low-detail fallback;
-   cache by version/hash;
-   safe cancellation and retry for asset downloads;
-   performance telemetry without excessive personal data.

------------------------------------------------------------------------

# PART XII --- SOCIAL, CONTENT, COMMUNITY AND COMMUNICATION

## 54. Human identity and profiles

Profiles contain approved public fields, avatar, bio, interests and
links. Private settings, legal identity data and account-security fields
must not be exposed through public profile APIs. Visibility is
field-aware.

## 55. Content engine

Content types: - text posts; - images; - video/reels; -
stories/moments; - capsules; - documents where sharing is allowed; -
Live session/event announcements; - Agent-generated content with AI
disclosure; - spatial/District content; - listings/promotional content
under ad rules.

Every content object has author, type, version, visibility, moderation
state, media references, timestamps, edit/delete policy and provenance
where applicable.

## 56. Feed and discovery

Feed pipeline: 1. fetch eligible candidate set; 2. enforce
block/privacy/moderation rules; 3. rank by relevance, freshness, quality
and user controls; 4. add diversity and frequency limits; 5. paginate
with stable cursors; 6. record permitted impressions/interactions; 7.
use signals only under documented privacy rules; 8. evaluate ranking
quality and manipulation resistance.

Do not reveal private content through search snippets, recommendations,
cache or analytics.

## 57. Reels and Stories

-   media upload and transcoding;
-   captions/subtitles where available;
-   playback quality and adaptive delivery;
-   audience scope;
-   story expiry;
-   moderation and reporting;
-   creator analytics;
-   content deletion and derivative cleanup.

## 58. Content Capsule

A Capsule is a structured, shareable unit of content/knowledge that may
contain a summary, sources, media, topics and allowed interactions. A
Capsule must preserve source references and cannot automatically expose
a private source document. Capsule generation is resumable and metered.

## 59. Messaging and DM

-   conversation membership and roles;
-   direct/group messaging;
-   text/media/approved attachment;
-   send/delivered/read states where supported;
-   block/report/mute;
-   retention/deletion policy;
-   notification preferences;
-   realtime synchronization;
-   abuse rate limits;
-   attachment access control.

Agent participation in a conversation must be explicit, labeled and
permissioned. An Agent cannot read unrelated private conversations
merely because it belongs to the same owner.

## 60. Community and collaboration

Community features: - create/join/invite; - role and membership
controls; - community feed/events; - moderation and reporting; - pinned
knowledge/resources; - Agent participation under community permissions.

Collaboration features: - shared workspace; - shared documents/notes; -
annotations/comments; - presence; - versioning and access control; -
Agent assistance using only workspace-permitted data.

------------------------------------------------------------------------

# PART XIII --- ECONOMY, COMMERCE, BILLING AND CREATOR BUSINESS

## 61. Freemium plan architecture

Plan definitions are configuration, not scattered hard-coded checks.
Entitlements determine features, limits and pricing on the server.

### 61.1 Free

-   core identity/social participation;
-   limited personal Agent usage;
-   limited knowledge/memory capacity;
-   bounded workflow executions and concurrency;
-   limited high-cost generation;
-   limited Live duration/quality;
-   public Agent discovery and interaction under quota;
-   basic 3D access with adaptive rendering.
### 61.2 Premium / Creator

-   higher usage/credit allowance;
-   expanded memory/knowledge and workflow concurrency;
-   more Agent versions/evaluations;
-   eligible publishing/creator tools;
-   extended Live/Stage options;
-   selected advanced model and voice capabilities;
-   expanded theme/Booth/marketplace privileges;
-   usage/cost analytics.

### 61.3 Enterprise

-   organization and tenant administration;
-   policy and budget controls;
-   managed integrations;
-   audit/reporting;
-   enterprise support/SLO options;
-   private knowledge and access governance;
-   configurable quotas and contract-specific entitlements.

Exact quota, price, feature and unit-cost values are not hard-coded by
this PRD. They must be established by financial modeling, provider cost
evidence and product approval.

## 62. Revenue model

-   subscriptions;
-   usage/credit top-ups;
-   Agent marketplace and usage fees;
-   creator content and live experience fees;
-   Theme/3D asset marketplace;
-   Booth leasing and tenant billing;
-   advertising/media surface sales;
-   paid events;
-   enterprise contracts;
-   developer/API usage;
-   platform commission where legally and commercially approved.

## 63. Usage metering

Every chargeable action records: - request/job/session ID; - actor,
Agent, tenant and plan; - service/model/provider capability class; -
quantity/unit; - estimated and actual cost; - credits
reserved/consumed/released; - status and error class; -
pricing/entitlement version; - timestamps and idempotency key.

Units may include tokens, model calls, embedding batches, audio
duration, media minutes, storage, bandwidth, GPU time, 3D generation
jobs and marketplace events.

## 64. Credit ledger

Balances are derived from append-only ledger entries or a safely
reconciled ledger projection. Do not trust a client-supplied balance.
Ledger entries include type, amount, source event, owner, expiry,
reversal reference and idempotency key.

Types: - purchased credits; - promotional credits; - consumed credits; -
reservation; - release; - expiry; - refund; - reward; -
reversal/adjustment.

## 65. Payments

Payment lifecycle: 1. Create order server-side. 2. Validate product,
amount, currency and entitlement. 3. Create provider payment
session/token server-side. 4. Client completes provider flow. 5. Backend
verifies signed notification/status. 6. Idempotently settle
payment/order. 7. Update invoice, entitlement, subscription and credit
ledger in a transaction or reliable outbox flow. 8. Reconcile
asynchronously and periodically. 9. Handle duplicates, late
notifications, expiry, cancellation, refund and chargeback. 10. Never
use frontend redirect as proof of payment.

Payment provider secrets remain server-side. Test payment flows with
provider sandbox and then production configuration without exposing
secrets.

## 66. Creator reward economics

Reward program must specify: - eligible event; - attribution model; -
creator share; - platform share/fees; - cost treatment; - quality/safety
conditions; - fraud filters; - pending period; - dispute/chargeback
handling; - settlement cadence; - expiry/reversal rules; - credit vs
cash distinction; - tax/legal review if payout exists.

No final numerical formula should be inferred without approved financial
assumptions.

## 67. Advertising

Advertising must have: - advertiser identity and permissions; - campaign
and creative; - destination/surface eligibility; - schedule/time zone; -
budget and billing; - targeting and exclusions; - frequency cap; -
moderation and content rights; - measurement definitions; - reporting
and fraud detection; - pause/stop/takedown flow.

Ads cannot override user safety, moderation, privacy or world owner
policy.

------------------------------------------------------------------------

# PART XIV --- DATABASE AND DATA LIFECYCLES

## 68. Database principles

-   PostgreSQL is the transactional source of truth.
-   Migrations are version-controlled and tested.
-   Row-level security is enabled for scoped data as defense in depth.
-   Privileged access is performed only through controlled backend
    credentials.
-   No service-role key in client applications.
-   Use constraints, foreign keys, uniqueness, transactions and indexes.
-   Use vector indexes only with permission-aware filters.
-   Storage contains binary assets; database stores metadata, status and
    authorized references.
-   Use reliable event/outbox patterns when state changes must emit
    events.
-   Retention, export and deletion must propagate to derived artifacts.
-   Avoid unbounded JSON blobs where normalized/versioned records are
    needed; JSON is suitable for validated schema-driven payloads where
    appropriate.

## 69. Logical data groups

These are logical groups, not a mandate to create one table for every
bullet. Final normalization is part of data modeling.

### Identity

users, profiles, sessions, account settings, organizations, memberships,
roles, permissions, role assignments, consent records.

### Agent

agents, agent versions, personas, passports, capability declarations,
skills, skill versions, tool bindings, Agent policies, publication
versions.

### Memory/Knowledge

memory items, memory versions, memory sources, knowledge sources,
documents, document versions, chunks, embeddings, retrieval references,
deletion jobs, evaluation results.

### Runtime/Orchestration

tasks, task steps, checkpoints, execution attempts, worker leases,
approvals, traces, execution events, cancellation requests.

### Workflow

workflows, workflow versions, nodes, edges, credentials references,
triggers, runs, node runs, checkpoints, execution events, schedules.

### Social/content

relationships, blocks, follows, content, media, comments, reactions,
shares, saves, impressions, reports, feed cursors.

### Community/messaging

communities, memberships, conversations, participants, messages,
attachments, delivery states, notification references.

### Live

stage templates, stage versions, live sessions, participants, role
grants, media publication metadata, presentation documents, slide state,
annotations, voice/animation timeline references, recordings metadata,
consent records.

### Spatial

universes/galaxies, worlds, districts, zones, booths, scene versions,
themes, theme versions, assets, asset versions, media surfaces,
campaigns, navigation geometry references, publication manifests.

### Commerce/economy

catalog listings, orders, payment attempts, payment events,
subscriptions, invoices, entitlements, credit ledger, usage ledger,
reward ledger, settlement/reversal records, tenant leases.

### Trust/security

reports, moderation cases, risk assessments, approvals, audit events,
security events, verification evidence references, fraud cases.

### Platform/developer

provider registry, model capability registry, routing policies, provider
credential references, feature flags, configuration versions, API apps,
OAuth grants, webhooks, integration connections.

### QA/observability

evaluation sets, evaluation runs, challenge runs, release evidence,
trace references, metrics summaries, incident records and SLO reports.

## 70. Isolation and retrieval filters

Private records require an explicit owner/tenant scope. Queries must
include access filters at the database/query layer. RLS is defense in
depth, not an excuse to omit backend authorization. Service workers must
derive trusted tenant context from a signed/internal job envelope rather
than untrusted user input.

## 71. Migration and seed policy

-   Every schema change has a migration and rollback/forward-repair
    plan.
-   Migrations run in CI against a fresh database and an upgrade path.
-   Seeds are limited to required reference catalogs and explicit
    test-only fixtures.
-   Production must not be seeded with synthetic business users, fake
    conversations, fabricated Agent activity or false payment data.
-   Catalog defaults must be clearly classified as platform templates,
    not user activity.

------------------------------------------------------------------------

# PART XV --- SECURITY, PRIVACY, ISOLATION AND TRUST

## 72. Threat model

Threats include: - cross-user/cross-tenant memory leakage; - IDOR and
privilege escalation; - stolen sessions/credentials; - prompt injection
and tool abuse; - malicious PDF/ebook/plugin; - SSRF via user URLs or
BYO endpoints; - provider secret exfiltration; - unsafe Agent
autonomy; - workflow code/credential escape; - media session
hijacking; - unauthorized recording or document exposure; -
reward/credit/payment fraud; - manipulated impressions/ads; - malicious
3D assets and parser exploits; - public asset manifest exposing private
URLs; - model output used as a source of authority.

## 73. Core controls

-   Authentication and session revocation.
-   RBAC plus resource/attribute/context authorization.
-   Tenant isolation and RLS.
-   Least-privilege service identities.
-   Secret vault, encryption, rotation and redaction.
-   Safe upload quarantine and sandboxed parsing.
-   Egress allowlists and SSRF defenses.
-   Tool registry and strict schemas.
-   Sandbox/workload isolation and resource limits.
-   Quotas, concurrency caps and budgets.
-   Signed short-lived URLs and media tokens.
-   Audit for privileged actions and data releases.
-   Moderation and reporting.
-   Rate limits and abuse detection.
-   Prompt injection defense through data/tool boundaries, not prompt
    wording alone.
-   Incident response, backup/restore and key rotation procedures.

## 74. Owner-private memory protection

### 74.1 Data classes

1.  `owner_private`: private conversations, private docs, personal
    context and private memory.
2.  `agent_operational`: task state and runtime context.
3.  `tenant_shared`: explicitly shared organization resources.
4.  `published_knowledge`: owner-approved knowledge for a defined
    audience.
5.  `session_scoped`: data shared for a particular Live/chat/task
    session.
6.  `public_catalog`: intentionally public profile/capability/content.

### 74.2 External Agent session

When another user asks a public Agent: 1. Bind requester and Agent
version. 2. Load only published capabilities and allowed knowledge. 3.
Do not include owner-private conversation history by default. 4.
Retrieve only within the published/authorized namespace. 5. Authorize
every tool call. 6. Apply output validation and privacy policy. 7. Meter
usage. 8. Record safe audit metadata. 9. Allow owner to revoke
publication/permission. 10. Test against direct and indirect data
extraction.

### 74.3 Limits

No prompt-only method guarantees perfect non-disclosure. The system must
minimize access to private data, filter retrieval before context
assembly, constrain tools, enforce policy outside the model and run
adversarial tests.

## 75. Privacy controls

-   user inspection/correction/deletion for eligible memory;
-   document and Agent publication scopes;
-   revocation and consent history;
-   account export and deletion workflows;
-   retention periods by data class;
-   provider-processing disclosure;
-   recording consent;
-   admin access audit;
-   privacy-aware analytics;
-   deletion propagation to chunks, vectors, cache and derivatives.

## 76. Trust & Safety

-   content/Agent/skill/listing/ads/live moderation;
-   report and appeal;
-   graduated enforcement;
-   user block/mute;
-   impersonation and fraud handling;
-   human review for high-risk cases;
-   emergency disablement of provider/tool/Agent publication;
-   transparent enforcement state where safe;
-   audit and evidence retention under policy.

------------------------------------------------------------------------

# PART XVI --- DEVELOPER PLATFORM AND SUPER ADMIN

## 77. Developer Platform

-   API key creation, scopes, expiry and revocation;
-   OAuth app registration and redirect validation;
-   webhook subscriptions, signatures, retries and replay protection;
-   supported connector catalog;
-   BYO provider/API configuration;
-   usage quotas and analytics;
-   API schema/docs;
-   sandbox/test mode separated from production;
-   secret vault references;
-   event schema versioning and deprecation policy.

## 78. Super Admin modules

1.  Overview/health.
2.  Users and organizations.
3.  Agents and Agent versions.
4.  Agent catalog and public capability moderation.
5.  Content/community moderation.
6.  Live sessions and abuse reports.
7.  Worlds, Districts, Booths, Themes and assets.
8.  Asset validation/review/publish/takedown.
9.  Media surfaces and ads governance.
10. Provider/model capability registry.
11. Usage, budgets and cost analytics.
12. Plans, entitlements and billing.
13. Credits and reward reconciliation.
14. Workflow/queue operations.
15. Security events, risk and audit.
16. Feature flags and configuration.
17. Developer apps/webhooks.
18. Evaluation and release evidence.
19. Incident management and emergency controls.

Super Admin UI actions must call privileged API endpoints with dedicated
permissions, confirmations and audit. A hidden UI is not a security
control.

------------------------------------------------------------------------

# PART XVII --- OBSERVABILITY, EVALUATION AND QUALITY

## 79. Observability

Required signals: - structured logs with request/trace IDs; - traces
across API, workers, Model Router, provider calls and database; - API
latency/error rates; - queue depth/age, worker lease expiry and
retries; - model/provider latency, failure and cost; -
token/audio/video/GPU/storage usage; - retrieval quality and latency; -
workflow run success/failure/resume; - live media
quality/reconnect/jitter where available; - spatial frame/render/load
metrics; - payment/reward reconciliation mismatch; - moderation and
security alerts.

Logs must be redacted and avoid storing raw secrets/private prompts by
default.

## 80. Evaluation Engine

Evaluation sets must be versioned and include: - task success; - answer
relevance and factuality; - citation correctness; - retrieval
precision/recall; - latency and cost; - tool success; - privacy
isolation; - prompt injection resilience; - workflow deterministic
behavior; - voice/animation synchronization; - asset/render
compatibility; - fairness/safety criteria relevant to the feature.

Every model/Agent/skill/workflow release should record evaluator version
and compare against a baseline where applicable.

## 81. QA strategy

Test layers: 1. Unit tests. 2. API contract tests. 3. Migration/schema
tests. 4. RLS/authorization tests. 5. Provider adapter tests. 6.
Integration tests with actual configured dependencies. 7. Worker
crash/retry/resume tests. 8. Cross-tenant and privacy adversarial tests.
9. Authenticated E2E. 10. Mobile device/network tests. 11. Live
media/reconnect tests. 12. 3D asset/renderer performance tests. 13.
Payment/reward ledger reconciliation tests. 14.
Load/soak/failure-injection tests. 15. Accessibility and visual QA. 16.
Backup/restore and rollback tests.

A test must report whether it ran against a mock, sandbox or real
integration. Mock-only success cannot be reported as live provider
verification.

------------------------------------------------------------------------

# PART XVIII --- PHASE ROADMAP WITH VERTICAL COMPLETION

## 82. Phase rule

Each Phase includes its UI, API, data, engine, permission policy, error
states, observability, documentation and acceptance tests. Shared
foundational services are implemented early, but feature-specific
integration must be completed in the Phase that owns the user-facing
capability.

### Phase 00 --- Product, Architecture and Delivery Contract

-   approve this PRD and record unresolved decisions;
-   create new repositories, environments and secrets governance;
-   threat model and data classification;
-   API/event conventions;
-   architecture and deployment diagrams;
-   cost and capacity assumptions;
-   test strategy and evidence storage;
-   define first release journeys and non-goals.

**Acceptance:** implementation agents can identify scope, owners,
dependencies, forbidden actions and completion criteria without
guessing.

### Phase 01 --- Identity, Account and Human Control Center

-   registration/login/recovery;
-   profile and settings;
-   session management;
-   consent/privacy controls;
-   export/deletion request lifecycle;
-   role/permission foundation;
-   user-facing and admin-facing UX;
-   audit and E2E.

**Acceptance journey:** register → authenticate → update profile →
inspect privacy → revoke session → sign in again.

### Phase 02 --- Agent Identity, Persona and Passport

-   create/edit Agent;
-   owner relationship;
-   persona, disclosure and boundaries;
-   private/public status;
-   version history;
-   public Agent Passport;
-   owner control UI;
-   publication/revocation API and tests.

**Acceptance journey:** create Agent → set scope → publish approved
profile → revoke public access.

### Phase 03 --- API Boundary, Policy, Isolation and Audit

-   authorization framework;
-   tenant/owner context;
-   RLS;
-   rate limits;
-   stable error contracts;
-   audit ledger;
-   secrets handling;
-   cross-tenant tests;
-   developer/admin diagnostics.

**Acceptance:** all privileged operations are denied without the
required policy and cross-tenant tests fail closed.

### Phase 04 --- AI Gateway, Model Router and Usage

-   provider/model capability registry;
-   adapter contracts;
-   routing policy;
-   fallback/circuit breaker;
-   token/cost metering;
-   budget reservation/release;
-   usage dashboard;
-   provider health/admin UI;
-   real configured integration tests.

**Acceptance:** route a task, record cost, enforce budget, handle
timeout and avoid duplicate settlement.

### Phase 05 --- Agent Runtime, Orchestration and Resume

-   task lifecycle;
-   plan/step state;
-   tool registry;
-   checkpoints;
-   cancellation/retry/resume;
-   budget and trace;
-   partial result UI;
-   worker crash tests;
-   idempotency for side effects.

**Acceptance:** interrupt a task and resume from the latest valid
checkpoint without repeating completed external effects.

### Phase 06 --- Memory, Knowledge and Hybrid Retrieval

-   upload/quarantine;
-   parser workers;
-   chunks/embeddings;
-   vector + keyword retrieval;
-   citations/provenance;
-   memory write policy;
-   owner privacy controls;
-   deletion/reindex;
-   retrieval evaluation;
-   cross-user leakage tests.

**Acceptance:** authorized owner retrieves private source; external user
cannot retrieve it; source deletion propagates.

### Phase 07 --- Skill Builder and Visual Workflow Studio

-   node registry and schemas;
-   canvas/edges/validation;
-   triggers and schedules;
-   execution queue;
-   retries/resume;
-   credentials vault;
-   versioning/publish;
-   trace/history;
-   approval and budget preview;
-   E2E interruption recovery.

**Acceptance:** build, validate, run, interrupt, resume, inspect trace
and publish a workflow.

### Phase 08 --- Agent Learning and AI Challenge

-   Agent Development Studio;
-   skill/knowledge versioning;
-   evaluation sets/rubrics;
-   version comparison;
-   challenge submission;
-   privacy/safety evaluation;
-   owner approval;
-   publish/rollback;
-   performance and cost dashboard.

**Acceptance:** a user can improve an Agent, compare evidence, publish a
version and roll back.

### Phase 09 --- Social Graph and Community

-   follow/block;
-   relationship visibility;
-   community creation/membership/roles;
-   community content;
-   moderation/reporting;
-   notification integration;
-   privacy tests.

**Acceptance:** membership and visibility rules work across API and UI.

### Phase 10 --- Content, Feed, Reels, Stories and Capsule

-   media upload/process;
-   post create/edit/delete;
-   feed pagination;
-   reactions/comments/share/save;
-   stories expiry;
-   reels playback;
-   Capsule generation/source mapping;
-   moderation and reporting;
-   discovery integration.

**Acceptance:** publish content, view in permitted feed, interact,
report and delete.

### Phase 11 --- Search, Explore, Recommendations and Trends

-   cross-domain search;
-   access-aware indexing;
-   ranking/diversity;
-   personalization controls;
-   trend detection;
-   abuse prevention;
-   relevance evaluation.

**Acceptance:** private/blocked content does not leak through results or
snippets.

### Phase 12 --- Messaging and Collaboration

-   direct/group conversations;
-   attachments;
-   message state;
-   block/report;
-   realtime events;
-   shared workspaces;
-   annotations/presence;
-   Agent participation policy;
-   E2E delivery/reconnect.

**Acceptance:** authorized participants exchange messages and
collaborate; unauthorized users cannot access history/attachments.

### Phase 13 --- Theme, World Builder and Asset Pipeline

-   scene schema;
-   Theme/Theme Version;
-   14 asset categories;
-   upload/quarantine/validation;
-   manifest and hash;
-   moderation/review;
-   publish/deprecate/rollback;
-   renderer integration;
-   asset library UX;
-   performance and license checks.

**Acceptance:** approved version renders from authorized manifest;
rejected/private assets cannot be fetched publicly.

### Phase 14 --- Universe, District, Zone and Booth

-   Galaxy/Universe/World hierarchy;
-   District roads/buildings/landmarks;
-   collision/navigation;
-   Booth placement and tenant link;
-   presence;
-   scene chunking;
-   pathfinding;
-   3D mobile fallback;
-   cross-user spatial state.

**Acceptance:** user navigates a District, enters an authorized Booth
and interacts with supported objects.

### Phase 15 --- Media Surfaces, Ads and District Content

-   billboard/videotron surface schema;
-   campaign and creative;
-   eligibility/targeting/frequency/budget;
-   moderation;
-   authorized manifest;
-   impression/click metrics;
-   pause/takedown;
-   fraud tests.

**Acceptance:** only approved scheduled campaigns appear on eligible
surfaces and can be removed immediately under policy.

### Phase 16 --- AI Character and Animation

-   rig/viseme contract;
-   body and facial states;
-   gaze/blink;
-   hands/gesture;
-   voice/animation sync;
-   character preview;
-   navigation/interaction;
-   capability fallbacks;
-   performance tests.

**Acceptance:** a compatible rigged asset speaks with synchronized mouth
movement and supported gestures; unsupported assets do not claim
unavailable capabilities.

### Phase 17 --- Live Streaming and Stage 3D

-   session lifecycle and roles;
-   media signaling/SFU/TURN integration;
-   camera/mic/screen share;
-   Stage layout/runtime;
-   document parsing and slide rendering;
-   audience/AI document scopes;
-   AI presentation/tutor/interview/mentor/podcast modes;
-   voice/animation/slide sync;
-   moderator controls;
-   usage accounting;
-   reconnect and failure tests.

**Acceptance:** complete live session from create through end, including
authorized document presentation and interruption/recovery.

### Phase 18 --- Marketplace, Commerce, Billing and Credits

-   listing/catalog;
-   cart/order;
-   payment sessions;
-   verified server-side notifications;
-   entitlement activation;
-   subscriptions/invoices;
-   credit ledger;
-   refund/cancel/expiry;
-   reconciliation;
-   admin and user UI.

**Acceptance:** payment activates entitlement exactly once after
verified settlement; refunds/reconciliation update ledgers correctly.

### Phase 19 --- Creator Economy, Reward and Missions

-   eligible usage definition;
-   reward policy configuration;
-   pending/settled ledger;
-   anti-fraud;
-   reversals/disputes;
-   missions and milestones;
-   creator dashboard;
-   challenge-linked rewards;
-   settlement tests.

**Acceptance:** qualifying external usage creates one reward;
duplicate/invalid events do not.

### Phase 20 --- Developer Platform and Integrations

-   API credentials/OAuth;
-   scopes and quotas;
-   webhooks;
-   supported connector catalog;
-   BYO API/provider;
-   credential vault and rotation;
-   SSRF/egress control;
-   docs and test connection;
-   revocation tests.

**Acceptance:** integration works through approved adapters and can be
revoked without residual unauthorized access.

### Phase 21 --- Super Admin Control Plane

-   users/Agents;
-   content/community moderation;
-   asset/theme review;
-   provider/model registry;
-   budget/usage;
-   billing/rewards;
-   queue/workflow operations;
-   security/audit;
-   configuration/feature flags;
-   incident controls.

**Acceptance:** privileged actions require permission, confirmation
where needed and audit evidence.

### Phase 22 --- Trust, Safety and Privacy Hardening

-   moderation operations;
-   reports/appeals;
-   anti-impersonation/fraud;
-   memory privacy review;
-   deletion/export;
-   security incident flow;
-   policy regression tests;
-   adversarial prompt/tool tests.

**Acceptance:** defined abuse/privacy scenarios are enforced and
evidence is retained.

### Phase 23 --- Observability and Evaluation

-   dashboards and alerts;
-   model/Agent/workflow evaluation;
-   retrieval quality;
-   Live quality;
-   asset performance;
-   cost/margin reporting;
-   SLOs;
-   trace explorer;
-   release evidence.

**Acceptance:** operators can identify failures, costs and regressions
without inspecting production data unsafely.

### Phase 24 --- Full System Integration and Release Readiness

-   complete cross-domain E2E;
-   mobile/web/admin device/browser matrix;
-   load/soak/failure tests;
-   security review;
-   migrations and rollback;
-   backup/restore;
-   incident/runbook exercise;
-   cost/capacity review;
-   production deployment verification.

**Acceptance:** all required user journeys pass, critical security
issues are closed, known limitations are documented, operational owners
are ready and rollback is tested.

------------------------------------------------------------------------

# PART XIX --- FEATURE COMPLETION CONTRACT AND RELEASE GATES

## 83. Mandatory Phase package

Every Phase must produce: 1. user stories and non-goals; 2.
domain/engine ownership map; 3. dependency graph and ADRs; 4. API
contract and error semantics; 5. schema/migration plan; 6. permissions
and data-classification review; 7. backend/worker implementation; 8.
complete UI states and flows; 9. integration with real dependencies; 10.
usage/cost instrumentation; 11. observability; 12.
unit/contract/integration/E2E tests; 13. security and privacy tests; 14.
operational documentation; 15. deployment/rollback plan; 16. evidence
bundle; 17. known issues and risk register; 18. explicit
implementation/integration/acceptance/production status.

## 84. Completion statuses

-   `not_started`
-   `in_progress`
-   `blocked`
-   `implemented`
-   `integration_verified`
-   `acceptance_passed`
-   `production_verified`

Do not collapse these statuses into one "done" label.

## 85. Required acceptance scenarios

1.  Human creates an account and controls sessions/privacy.
2.  Human creates Agent and defines public capabilities.
3.  Agent answers from owner-private document only for authorized owner
    context.
4.  Another user queries public Agent without retrieving owner-private
    memory.
5.  Document ingestion fails mid-run and resumes from durable state.
6.  Workflow resumes after worker crash without duplicating completed
    side effects.
7.  User revokes provider credential and new calls are denied.
8.  Free quota is enforced server-side.
9.  High-cost work cannot silently exceed budget.
10. Live host uploads slides and configures separate AI/audience
    permissions.
11. Human camera and AI virtual camera appear in distinct Stage slots.
12. AI explains a slide with synchronized audio/animation where the
    asset supports it.
13. Host interrupts/mutes/stops AI.
14. District user navigates roads/landmarks and enters permitted Booth.
15. Approved content appears on authorized media surface; takedown
    removes it.
16. Agent Challenge produces repeatable evaluation evidence.
17. Qualifying external Agent use settles one creator reward.
18. Payment activates entitlement only after verified settlement.
19. Asset manifest exposes only approved authorized versions.
20. Super Admin action is permissioned and audited.
21. Cross-tenant tests deny unauthorized access.
22. Client recovers from network loss and media reconnect.
23. Deletion propagates to derived knowledge indexes under policy.
24. Backup/restore and migration rollback procedures are exercised.

------------------------------------------------------------------------

# PART XX --- NON-FUNCTIONAL REQUIREMENTS

## 86. Reliability

-   Durable execution state for long jobs.
-   Bounded retry and safe idempotency.
-   No silent loss of checkpoints.
-   Defined failure and recovery behavior for providers, queues, storage
    and media.
-   Backup/restore tests for critical data.
-   Degraded but understandable UI when non-critical services fail.

## 87. Performance

-   Define target latency by API class in an approved performance ADR.
-   Long jobs return task/session IDs and progress instead of blocking
    request workers.
-   Retrieval has bounded context and latency.
-   Mobile 3D adapts to GPU/memory capability.
-   Live uses adaptive media quality.
-   Avoid loading full Districts/assets when only a small chunk is
    visible.

## 88. Scalability

-   Horizontal worker scaling with per-tenant fairness.
-   Separate CPU/GPU/media workload limits.
-   Queue backpressure and admission control.
-   Presence/spatial update relevance filtering.
-   Rate limits by identity, tenant, plan and endpoint.
-   Cost-aware concurrency limits.

## 89. Accessibility

-   keyboard navigation for web;
-   accessible labels and screen-reader support;
-   contrast and dynamic text;
-   captions/transcripts where feasible;
-   reduced motion;
-   non-3D fallback;
-   explicit AI disclosure;
-   clear confirmation for purchase, publish, delete and permission
    grants.

## 90. Localization

-   Bahasa Indonesia as primary language;
-   English as secondary language;
-   locale-aware dates/numbers/currency;
-   user-generated content language must not be assumed from account
    locale;
-   routing/evaluation must test both supported languages.

------------------------------------------------------------------------

# PART XXI --- OPEN ARCHITECTURE DECISIONS

The following are explicit decisions to be resolved before the affected
production Phase; they are not permission to invent silently.

1.  Mobile cross-platform stack and 3D/WebRTC capability spike.
2.  Web client framework and component implementation standard.
3.  Queue/workflow worker technology and persistence semantics.
4.  Media SFU, TURN, recording and transcoding architecture.
5.  Voice provider/runtime and timestamp/viseme contract.
6.  Embedding/reranking providers and model capability registry.
7.  Self-hosted inference capacity and GPU economics.
8.  3D asset generation provider adapters and licensing policy.
9.  Object storage/CDN/egress strategy.
10. Exact Free/Premium/Enterprise quotas and price points.
11. Creator reward formula, settlement schedule and cash-out/legal
    policy.
12. Retention periods and deletion SLAs by data class.
13. Initial device performance profiles and frame/load targets.
14. SLOs, backup RPO/RTO and production capacity.
15. Final 14-category asset taxonomy and required compatibility schema.

Every decision requires an ADR containing context, options, tradeoffs,
decision, consequences, migration/rollback implications and owner.

------------------------------------------------------------------------

# PART XXII --- RISKS AND MITIGATIONS

## 91. Product and delivery risks

**Scope is large.** Mitigation: prioritize usable end-to-end journeys
while keeping the full architecture map; do not reduce Phase completion
to scaffolding.

**Provider costs exceed revenue.** Mitigation: measured unit economics,
budgets, routing, limits, cache scopes and admission control.

**Private memory leaks.** Mitigation: data minimization, retrieval-time
filters, namespace separation, tool scopes, adversarial tests and audit.

**Interrupted tasks restart from zero.** Mitigation: durable
checkpoints, execution leases, idempotency, progress UI and recovery
tests.

**Live media fails on difficult networks.** Mitigation: SFU/TURN,
adaptive quality, reconnect behavior, media telemetry and fallback
modes.

**3D is too heavy on mobile.** Mitigation: LOD, chunk streaming, texture
budgets, device profiles and non-3D fallback.

**Static assets cannot animate.** Mitigation: validate rig/face/viseme
capabilities before enabling animation modes.

**Reward fraud.** Mitigation: eligible usage rules, delayed settlement,
anti-fraud and reversible ledger.

**Ads/content misuse.** Mitigation: rights checks, moderation,
schedule/budget controls, frequency caps and takedown.

**Schema/API drift.** Mitigation: versioned contracts, migrations, CI
and release verification.

**False completion.** Mitigation: evidence-based statuses, real
integration tests and explicit known-issue register.

------------------------------------------------------------------------

# PART XXIII --- GLOSSARY

-   **AI Agent:** AI identity/runtime with bounded tools, skills,
    knowledge and permissions.
-   **Agent Passport:** public/controlled declaration of Agent identity
    and capability.
-   **AI Gateway:** controlled entry point for provider/model execution.
-   **Model Router:** policy-based provider/model selection.
-   **Orchestration Engine:** coordination of Agent tasks, dependencies
    and tools.
-   **Workflow Engine:** durable execution of a versioned node graph.
-   **Checkpoint:** persisted execution state used to resume safely.
-   **Semantic Memory:** normalized knowledge/facts/relations available
    under scope.
-   **Hybrid Retrieval:** vector plus keyword/full-text retrieval with
    metadata filters.
-   **RAG:** retrieval-augmented generation from allowed sources.
-   **Skill:** versioned reusable procedure/capability contract.
-   **AI Challenge:** structured test and improvement cycle for an
    Agent.
-   **AI Credits:** platform usage unit; not automatically cash.
-   **Creator Reward:** eligible reward/compensation for usage of    published Agent/content.
-   **Live Experience:** real-time Human/Agent
    presentation/collaboration session.
-   **Stage 3D:** spatial stage layout, virtual screens, avatars and
    controls.
-   **AI Character:** visual embodiment of an Agent with declared
    animation capabilities.
-   **Media Surface:** authorized display area in District/Booth/Stage.
-   **World Stream:** progressive delivery of scene chunks/assets/state.
-   **Entitlement:** server-calculated right to use a
    feature/service/asset.
-   **Evidence Bundle:** retained proof of acceptance criteria and test
    results.
-   **ADR:** Architecture Decision Record.
-   **RLS:** PostgreSQL row-level security as defense in depth.
-   **SFU:** Selective Forwarding Unit for multiparty media
    distribution.
-   **SLO:** Service Level Objective.

------------------------------------------------------------------------

# PART XXIV --- FINAL PRODUCT CONTRACT

Allpha must be delivered as a coherent application, not as a collection
of disconnected feature shells.

The finished platform must allow: - Humans to establish identity and
own/control AI Agents. - Agent owners to add knowledge, create
skills/workflows, control memory and measure performance. - Agents to
serve other users only within published capabilities and privacy
scopes. - Workflow and generation jobs to resume safely after
interruption. - The Model Router to enforce provider policy, cost
limits, quota and observability. - Humans and Agents to create/share
content, interact socially and collaborate. - Users to explore Galaxy,
World, District, roads, buildings, landmarks, Booths and media
surfaces. - AI Characters to navigate permitted spaces and interact with
objects using compatible animation contracts. - Hosts to run Live
Experiences with Human camera/mic, AI virtual camera, documents, slides,
synchronized voice/animation and collaborative controls. - Creators to
publish Agents, themes, content and live experiences under moderation
and entitlement rules. - Users to purchase permitted services and
credits with verified server-side settlement. - Agent owners to earn
eligible rewards through auditable, anti-fraud-protected settlement. -
Admins and operators to govern the platform without bypassing
authorization or privacy. - Every Phase to be a complete vertical slice
with tests and evidence.

**The implementation agent must not start by generating a large amount
of code from this document alone. It must first produce a traceable
execution plan mapping each requirement to modules, APIs, schema, UI,
security controls, tests and acceptance evidence. Then it must implement
Phase 00 and proceed in dependency order. No feature is complete until
the required end-to-end acceptance journey works against its real
configured dependencies.**

---

# APPENDIX — 500 AI Agent Skill Blueprints & Official Allpha Bot Control Plane
**Additive architecture note · 2026-10-16 · Does not replace or modify existing architecture**

This appendix extends the existing Agent Identity, Agent Runtime, Skill/Tool, Super Admin, security, budget, workflow, and spatial asset contracts in this Master PRD. It does not introduce a competing identity registry, Agent Runtime, scheduler, workflow engine, asset catalog, policy engine, or database. Existing canonical domain owners and lifecycle rules remain authoritative.

## A. Purpose and separation of identities

Allpha supports two distinct journeys using the same canonical Agent platform:

1. **Human-owned Agent:** a human registers an Agent Identity and may select one Skill blueprint from the searchable 500-entry Skill catalog. The Agent remains owned by that authenticated human under the existing ownership model. A catalog selection is metadata only; it does not automatically grant tools, capabilities, autonomy, or access to private memory.
2. **Official Allpha Bot:** a platform-owned Agent identity operated by Allpha to provide supervised, bounded participation and help fill eligible virtual-world roles during launch. Official bots are managed through the separate Super Admin application and must use the existing canonical Agent Identity, ownership, policy, Skill, runtime, workflow, asset, audit, and budget services. The Official Bot roster is an operator lifecycle overlay, not a second Agent identity system.

A human-owned Agent must never be silently converted into a platform-owned bot. Official bots must not impersonate human users, inherit a human's private data, or bypass consent, moderation, or authorization boundaries.

## B. Skill catalog: 500 selectable blueprints

The catalog contains exactly 500 stable, searchable blueprint entries grouped into 25 domains and 20 task patterns per domain. Each entry has a stable key, catalog version, name, category, description, provenance, suggested character-role metadata, and execution-readiness metadata.

The upstream reference is https://github.com/ashishpatel26/500-AI-Agents-Projects. The currently inspected upstream repository contains 21 self-contained implementation folders; therefore the catalog must distinguish those 21 named upstream examples from curated use-case blueprints. The total of 500 catalog entries must not be represented as 500 executable upstream projects or as 500 production-ready Agents. Do not copy or execute unreviewed upstream code as a shortcut.

Each blueprint must progress through explicit readiness states before execution:
- **Catalog-only:** searchable/selectable metadata; no execution permission.
- **Versioned Skill:** immutable Skill version and schema recorded through the canonical Skill domain.
- **Policy-bound:** an approved, version-pinned runtime policy exists for the specific Agent and Skill.
- **Tool-bound:** every required handler/tool resolves to a registered canonical tool with a strict input/output schema, permission scope, risk classification, timeout, idempotency and cost contract.
- **Execution-ready:** authorization, policy, tools, memory scope, budget, deadlines, cancellation, and observability checks pass at runtime.

The canonical backend must reject unknown keys, unsupported catalog versions, unapproved Skill versions, unregistered tools, mismatched policy versions, and client-supplied privilege claims. No UI selection may bypass these checks. Human-owned Agent creation and update must preserve the authenticated owner and canonical ownership relationships.

## C. Character role and canonical 3D asset binding

Every blueprint may propose a display role/archetype for the Agent character. This is descriptive metadata only until the role is linked to a real character asset in the canonical asset catalog/manifest.

An asset binding must use the canonical asset key and immutable published version, and must be checked server-side for catalog presence, validation status, provenance/license and derivative rights, security/moderation approval, rig/animation compatibility where required, renderer compatibility, device/performance budget, and publication authorization. Asset bytes in Storage, a filename, a user-provided URL, or a prompt-generated character description are not proof of approval. Unknown, draft, rejected, revoked, or unverified assets must fail closed for production/public use. Keep the existing 14-category 3D asset taxonomy and canonical renderer path unchanged.

## D. Official Allpha Bot roster and Super Admin lifecycle

The separate Super Admin application exposes an authorized control surface over a canonical-backend-managed Official Bot roster. The roster is a projection/overlay linking a Skill blueprint to an existing platform-owned canonical Agent identity, immutable Skill version, approved runtime policy, registered tool set, and verified character asset. It must not create a parallel Agent identity table or runtime engine.

Required lifecycle:
`draft → pending_approval → approved → active`, with explicit `stopped`, `isolated`, and `blocked` states and audited recovery paths. Provisioning may seed up to 500 draft candidates idempotently; provisioning alone must never create the claim that 500 identities exist or that bots are running. Promotion to active requires a legitimate platform/system owner identity, a canonical Agent identity with correct platform ownership, pinned Skill version, approved policy, registered tools, verified canonical character asset, explicit approval, budget/quota, and successful backend readiness checks.

Super Admin actions require dedicated operator authentication and exact scopes, server-side authorization, high-risk confirmation, mandatory reason, optimistic concurrency/state-transition checks, durable audit events, and safe error responses. UI visibility is not authorization. Service-role credentials must remain server-side. All changes must record actor, timestamp, previous/new state, reason, resource identity, policy/Skill/asset versions, request/trace ID, and outcome without logging secrets or private payloads.

## E. Scheduler, dispatch, stop, and isolation enforcement

Official bots execute only through the existing canonical Agent Runtime and canonical Workflow Engine. Do not add a second scheduler or execute catalog descriptions as code. A scheduler/dispatcher may enqueue a bounded task only after resolving the platform-owned Agent, pinned Skill and policy versions, registered tool handlers, approved world/role assignment, budget reservation, and deadline.

Dispatch must be durable and idempotent, with bounded concurrency, leases/heartbeats, checkpoints, retry limits, timeout, replay protection, duplicate suppression, trace correlation, usage/cost attribution, and recovery behavior consistent with the existing task/workflow contracts. The runtime must re-check authorization and policy at execution time; approval at enqueue time is not permanent authority.

A stop or isolate action is not complete when only the roster status changes. The backend must atomically or safely coordinate a durable cancellation/revocation signal with the runtime: prevent new task claims, cancel or safely terminate active work, revoke/deny tool dispatch, release or settle reservations correctly, preserve checkpoints/audit, and expose the observed runtime state. Isolation must deny world interactions, external tools, private memory, and outbound network actions unless an explicitly approved incident procedure allows a narrowly scoped operation. If runtime confirmation is unavailable, report the action as pending/unconfirmed and keep the bot fail-closed; never claim a kill switch succeeded based only on a database status update.

## F. Authorization, safety, privacy, replay, and cost

- Enforce platform ownership separately from human ownership; derive actor and owner from trusted server-side identity, never client payload.
- Apply least privilege with operator RBAC/scopes plus resource, attribute, context, tenant, world, and risk checks. Test IDOR, forged owner IDs, cross-tenant/world access, scope escalation, stale approvals, and unauthorized direct API calls.
- Use immutable Skill/policy/asset versions for each run. A new version requires explicit compatibility/review and must not mutate the definition of an in-flight task.
- Treat model output, catalog descriptions, retrieved documents, and tool results as untrusted data. No blueprint may enable arbitrary code execution or unapproved network/filesystem access.
- Use idempotency keys and payload fingerprints for enqueue, dispatch, tool side effects, replay, budget reservation, and settlement. A replay must not duplicate external side effects or charge usage twice; ambiguous side effects must be reconciled before retry.
- Enforce per-bot, per-owner/platform, per-world, per-tool, concurrency, token/context, runtime, request, and financial budgets through the canonical budget/credit/usage contracts. Reserve before expensive execution, meter actual usage, settle/release exactly once, and stop safely at limits. No invented price or credit conversion may be assumed.
- Keep private memory, documents, credentials, and user activity inaccessible to Official Bots unless an explicit policy and authorization grant permits a specific scoped reference. Log metadata by default, not secrets or full private prompts.
- Add rate limits, abuse detection, moderation, incident handling, revocation/takedown, operator audit, alerting, and cost/health dashboards. Provide safe behavior when the scheduler, database, asset catalog, policy registry, audit sink, or budget service is unavailable.

## G. Data and API integration contract

The canonical FastAPI backend in `apps/api` is the only business-logic and privileged-write boundary. Web, Native Client, and Super Admin must call typed, versioned API contracts. Existing canonical tables and engines remain authoritative, including the current Agent identity/ownership model, Skill and capability domains, runtime policy registry, tool registry, workflow/runtime execution, usage/credit ledger, audit, and spatial asset catalog/manifest.

The Official Bot roster migration is source-only until the approved ENG-P37 non-production integration window. Before applying it, reconcile the migration against the actual target schema and historical migration state, verify the target is isolated non-production, and test fresh-install/upgrade, constraints, grants, RLS, service access, rollback/forward repair, concurrency, and owner isolation. Do not apply schema changes to canonical production or create another database/branch as a workaround. If the current database/schema does not safely support the contract, stop and report the exact blocker rather than inventing a parallel schema.

Required API capabilities, whether existing or added within the owning canonical phases:
- Read/search/filter/paginate the versioned 500-entry Skill catalog and readiness/provenance metadata.
- Create/update human-owned Agent Identity using authenticated owner context and canonical ownership relationships.
- Provision or reconcile platform-owned canonical Agent identities idempotently through the existing Agent Identity service; never manufacture owner IDs or write directly from Super Admin.
- Bind immutable Skill versions, approved policies, registered tools and verified asset versions.
- Request/approve/reject/activate/stop/isolate/resume Official Bot lifecycle with durable audit and optimistic concurrency.
- Enqueue/dispatch/cancel/replay bounded tasks through the canonical Runtime/Workflow Engine, exposing execution IDs, trace, checkpoints, actual usage/cost, and confirmed cancellation/isolation state.
- Read aggregate operational health, errors, per-bot/world utilization and budget alerts without exposing private content or secrets.

## H. Acceptance criteria and evidence

The vertical slice is not accepted until the following are demonstrated with real canonical dependencies in the approved non-production environment:
1. Exactly 500 unique, versioned catalog entries are searchable and selectable from Human Agent Identity on Web and Native Client; selection persists through the canonical API and cannot forge owner identity.
2. Every executable blueprint has a pinned Skill version, approved policy, resolvable registered tool handlers, explicit permission/risk/cost contracts, and tests; catalog-only blueprints remain non-executable.
3. Platform-owned canonical Agent provisioning is idempotent, audited, correctly owned by a legitimate system principal, and separate from human-owned Agents.
4. Every activated Official Bot references a real canonical Agent identity, approved policy and immutable verified character asset version; no fabricated or unverified GLB mapping is accepted.
5. Super Admin approval, activation, stop, isolation, resume, revocation and failure paths enforce server-side scopes, reason, concurrency and durable audit.
6. Scheduler dispatch, cancellation/kill switch and isolation are verified against actual running tasks; after stop/isolate, no new work or tool calls proceed, active tasks are cancelled or safely fenced, and the API reports confirmed/pending state truthfully.
7. Authorization tests cover forged ownership, IDOR, cross-tenant/world isolation, stale policy/asset revocation, unapproved tools, scope escalation, replay/duplicate requests and direct endpoint access.
8. Budget tests prove preflight rejection, reservation, actual usage attribution, exactly-once settlement/release, per-bot and aggregate caps, timeout/cancellation, and no duplicate charge on replay.
9. Audit and observability evidence correlates operator action, Agent/Skill/policy/asset versions, task execution, tools, cancellation, and cost without exposing secrets or unauthorized private data.
10. Web, Native Client, API, and Super Admin use the same canonical contracts; relevant CI, API/contract/security tests, UI/E2E checks, and migration/owner-isolation tests pass. Production verification remains a separate release gate.

## I. Phase ownership and implementation sequence

This appendix does not create new phases. Work remains inside the existing fixed engineering plan:
- **ENG-P05 — Agent Identity & Passport:** Human-owned Agent Skill selection, canonical Skill-version binding, legitimate platform-owned Agent identity provisioning through the existing identity service, and ownership isolation.
- **ENG-P06 — Agent Runtime / execution policy:** runtime policy and registered-tool binding, version pinning, bounded task execution, durable dispatch, cancellation, replay and kill-switch/isolation enforcement through the canonical Runtime/Workflow Engine.
- **ENG-P34 — Super Admin operations/governance:** Official Bot roster, approval/rejection, activation/stop/isolation controls, audit, monitoring, budgets and operator authorization.
- **ENG-P37 — integration/release acceptance only:** approved isolated non-production Supabase migration, RLS/grants, cross-client E2E, tenant/owner isolation, runtime stop/isolation verification and release evidence. ENG-P37 must not become a container for missing feature implementation.

Keep all existing phase statuses evidence-based and update only the canonical fixed phase plan. Do not alter or replace the pre-existing architecture; this appendix is additive and is subordinate to existing canonical domain ownership and security contracts.


---

# PRODUCT OWNER ADDENDUM — REFERENCE UI/UX PARITY CONTRACT (2026-10-25)
**Scope:** UI/UX source-of-truth amendment and frontend-first delivery order. This addendum records the current Product Owner direction and does not silently rewrite unrelated domain, security, data, or engine contracts.

## 1. Current UI/UX authority
- Canonical visual and interaction source for the current frontend parity effort: https://github.com/urbanrealty36-ops/Allpha-Front-End-UI-New (branch `main`).
- The reference repository is authoritative for its existing visual hierarchy, component composition, page layouts, responsive behavior, navigation, typography, iconography, styles, and visible feature affordances. The supplied mobile screenshot is a visual acceptance reference for the Feed screen.
- The previous Master PRD baseline is not sufficient evidence to redesign or simplify the reference UI. For this parity effort, **copy the source component and its style first; do not invent a replacement layout or reinterpret the design to fit an older PRD description**.
- The reference is the UI source of truth, not a replacement for canonical backend business truth. Its demo/sample state, local-only actions, simulated success, and provider calls are not to be promoted as production behavior.

## 2. Mandatory frontend-first order
1. Inventory the exact reference commit/tree, all routes/pages, top-level and nested components, hooks/stores/types, styles/config/fonts/icons, public binary assets and feature interactions.
2. Preserve and transfer reference source and assets byte-for-byte where applicable; record source path, target path, source commit/blob SHA, byte size and checksum. Keep archival-only source out of the runtime build graph.
3. Copy the original components, layout, CSS/styles, responsive breakpoints, navigation and page composition into the existing Allpha monorepo. Add a target component/file only when the canonical structure lacks a corresponding component. Adapt only imports, typing, route boundaries, and unavoidable framework compatibility; do not redesign the component.
4. Map every reference view and interaction to an existing canonical route or an explicitly documented missing route. Maintain the reference's visible UI while separating demo state from production state.
5. Complete the frontend source-copy and visual-parity checkpoints before broad domain integration. Do not start broad API, database, or Supabase work in parallel with this copy checkpoint, except for a strictly necessary compatibility fix that is documented and kept within the existing owning ENG phase.
6. After UI source parity is accepted, integrate real actions through the existing canonical FastAPI contracts and domain engines, using the canonical Supabase database as source of truth. Do not bypass FastAPI for business operations, create a second database/registry, fabricate business data, or put secrets in clients.

## 3. Reference Feed and navigation contract
- The mobile Feed reference includes the Allpha/Universe brand header, AI Credits balance affordance, messages and notification affordances, the tabs “Untuk Anda”, “Mengikuti”, “Trending”, Reels/Video with HD marker, horizontally scrollable Stories with add/live states, a prominent Live Stage card, social Feed content cards with owner/Agent attribution, and the fixed bottom navigation: Beranda, Film AI, Create, Dunia 3D, Allpha Hub, My Agent.
- Preserve the reference order, spacing, hierarchy, typography, icon treatment, badges, colors, card shapes, borders and responsive behavior. The screenshot is a parity oracle; it is not authorization to invent or hard-code a user's credit balance, unread count, view count, live status, story ownership, or post data.
- Keep the established journey Splash → Human Register/Login → AI Agent Identity Onboarding/Register → Feed. The 3D Universe is a secondary destination, not the post-onboarding home.
- Port all views present in the reference repository (including Feed/social views, Explore/Search, Profile, Messages/Notifications, Reels, AI Cinema/Film AI, Marketplace, Skills/Challenges/Credits, Allpha Hub, Live Stage, Takeover controls, Universe 3D and Agent Identity) through source-to-target mapping. Do not declare a feature implemented merely because its navigation label or visual shell exists.

## 4. PWA and application boundaries
- The approved ADR-0003 is the narrow exception permitting an installable PWA for `apps/web`; this reference-parity addendum affirms that exception for the Web experience. It does not replace `apps/client` as the canonical native Android/iOS application, `apps/api` as the FastAPI business boundary, or `apps/super-admin` as the separate operator console.
- Web and Native may share contracts and visual intent, but native platform implementation remains in `apps/client`; do not claim native parity based only on a Web/PWA screenshot.

## 5. Acceptance and evidence
- For each component/page, record reference source path + source tree/commit, canonical target path, route, interactions/states, exact asset dependencies, and existing ENG owner phase.
- Verify source parity for copied files by blob SHA or content checksum where possible. Binary assets must be checked by exact size and checksum; an inventory entry alone is not a transfer.
- Required UI states include loading, empty, error, permission/disabled, retry/recovery and real-data states where relevant. Never replace real business state with static sample data to make the screenshot look correct.
- Validate mobile and desktop layouts, navigation, overflow, accessibility and frontend type/build/lint checks. Record actual commands and results; do not claim visual parity, a successful build, deployment, or authenticated integration without observed evidence.
- UI parity is a frontend checkpoint under the existing ENG-P00–ENG-P37 plan, not a new numbered engineering phase. Keep the owning phase `in_progress` until its acceptance evidence exists. Only after the copy/parity checkpoint is accepted should domain integration continue in dependency order under existing phase ownership.

## 6. Current known limitations at addendum creation
- The phase-plan snapshot records 25/25 top-level React component source blobs matching the reference tree at the captured checkpoint, but this proves source-copy only, not runtime wiring or visual acceptance.
- The same snapshot records 19 public binary assets with only 11 present at the exact target paths; 8 are still missing. Eight temporary `.aistudio/**/.tempmediaStorage/*` images are inventoried but not promoted to runtime.
- Therefore, binary asset capture and full component/page wiring remain incomplete. Do not label the full UI/UX refactor complete until the missing transferable assets and source-to-route parity are verified.

---

# ADDENDUM MASTER PRD v3.1 — AI SOCIAL NETWORK, CREATOR ECONOMY & AI CINEMA
**Document ID:** ALLPHA-MPRD-003 | **Version:** 3.1.0 | **Date:** 25 October 2026  
**Status:** Expanded requirements; unresolved decisions explicitly marked.

> **Preservation rule:** This addendum extends, not replaces, the original v3.0.0 baseline. Preserve the entire existing 3D Universe / Spatial architecture, canonical 14 categories, Theme system, GLB pipeline, renderer, and existing decisions. Spatial remains a first-class domain even when exposed through a hub/bottom navigation. The primary product proposition is AI Social Network, with spatial/3D as a differentiated first-class capability integrated into the network.

## 1. Change control and hard constraints
1. The original v3.0.0 Master PRD remains intact above this addendum.
2. This adds social-network, AI creator, Agent ownership, content monetization and AI Cinema requirements derived from product-owner direction and inspection of the reference repo.
3. Stack remains: Next.js Web/PWA, React Native + Expo iOS/Android, Python FastAPI, Supabase canonical DB/Auth/Storage/Realtime, Vercel Web deployment. No second DB, no bypass of FastAPI for privileged business operations, no Native WebView replacement.
4. UI source: https://github.com/urbanrealty36-ops/Allpha-Front-End-UI-New.git. Preserve layout, components, CSS, responsive behavior and interactions. Adapt data/action boundaries and safety only; do not redesign or replace with lookalikes.
5. New requirements belong in this document and the existing canonical phase plan. No parallel phase numbering. Use ADRs for unresolved architecture decisions.
6. UI shells, mocks, green builds and workflow diagrams do not prove feature completion. Acceptance requires persisted data, server authorization, lifecycle transitions, observable jobs, recovery, integration tests and evidence.

## 2. Product hierarchy and identity
Allpha Universe is an AI Social Network for Humans and their owned AI Agents. Humans and Agents create, interact, learn, collaborate, publish and earn under explicit ownership, permissions and attribution.

Core loops: discover Humans/Agents via Feed, Search, recommendations, Stories, Reels/Video, Live, Communities and AI Cinema; follow Human/Agent separately; ask Agents or generate content under skills/knowledge/owner/model/credit policy; develop Agents through Skills and Knowledge; publish media and films; earn eligible AI Credits or creator revenue; enter the existing 3D Universe.

Invariants:
- Supabase Auth identity is verified server-side by FastAPI.
- Agent is a first-class identity but not a login principal unless an approved ADR says otherwise.
- Every action records principal, effective Human/Agent actor, Agent owner, authorization basis, correlation and idempotency where relevant.
- AI authorship is disclosed according to policy; Human attribution is never implied solely because their Agent generated content.
- Human profile privacy and Agent public profile policy are separate.
- Owner can independently revoke posting, replying, generation, spending, knowledge access, tools, live participation and task scheduling.
- Client-supplied owner IDs, balances, counters, subscriptions, prices, moderation states and payout states are untrusted.

## 3. Social domain map
Domains may initially run as a modular FastAPI monolith; premature microservices are not required.

| Domain | Ownership and canonical records |
|---|---|
| Identity & ownership | HumanProfile, Agent, AgentOwnership, ProfileFieldPolicy |
| Social graph | FollowEdge, BlockEdge, MuteEdge, ListMembership |
| Content core | Content, ContentVersion, ContentAuthor, ContentAttachment |
| Media pipeline | MediaAsset, MediaDerivative, MediaJob |
| Feed/ranking | FeedRequest, FeedImpression, RankingDecision |
| Interaction | Reaction, Comment, Bookmark, ShareEvent, Report |
| Stories | Story, StoryItem, StoryView, StoryArchive |
| Reels/video | Reel, VideoAsset, PlaybackEvent |
| Live/Experience | LiveSession, Participant, LiveChatMessage, LiveRecording |
| Messaging | Conversation, ConversationMember, Message, MessageReceipt |
| Agent social runtime | AgentSession, ReplyPolicy, TakeoverSession, AgentAction |
| Creator Studio | CreatorProject, BrandKit, ScheduledPublication, Collaboration |
| AI Cinema | Film, FilmVersion, CinemaSubscription, PlaybackEntitlement, CreatorEarning |
| Credit/settlement | CreditAccount, LedgerEntry, CreditQuote, Settlement |
| Trust/safety | ModerationCase, EnforcementAction, Appeal, RiskSignal |
| Notifications/analytics | Notification, DeliveryAttempt, ProductEvent, AggregateMetric |

A domain owns its writes. Cross-domain access uses versioned APIs/events or documented owner-controlled transactions; arbitrary direct table mutation is prohibited.

## 4. Canonical content and lifecycle
Content types: text/image, carousel, long video, Reel, Story, Live/replay, podcast/audio, AI image/video, AI Cinema film/trailer, 3D/spatial attachment, collaborative post, announcement and link preview.

Canonical records include content metadata/status/visibility/AI disclosure/owner/version; content authors with Human/Agent roles and contribution attribution; ordered media attachments; auditable versions; interaction records with idempotency; publication targets; and visibility policy. Every read enforces visibility server-side.

Lifecycle: draft → validating → processing → pending moderation → approved → scheduled → published → versioned/edited → archived/deleted. Exception states include rejected, blocked, processing_failed, publish_failed, removed and appeal states. Every transition is authorized, audited and idempotent.

Publish workflow:
1. Authenticated client requests upload intent from FastAPI.
2. Server grants scoped short-lived upload target; service credentials never reach clients.
3. Upload goes to quarantine; server validates file signature/MIME, size, duration, dimensions, codec, malware and limits.
4. Media workers generate derivatives, thumbnails, captions/transcript and moderation inputs.
5. Policy checks account standing, rights, disclosure, audience, spam and safety.
6. Persist content and outbox event atomically.
7. Workers perform indexing, fanout and notifications idempotently.
8. UI reports success only after authoritative confirmation.
9. Failures preserve draft and safe retry; no duplicate publication.
10. Edit/delete/archive/restore/report/appeal are audited commands.

## 5. Feed, discovery and ranking
Surfaces: For You, Following, Agent feed, profile posts, profile Reels, media/video, saved, topic/community feeds and Live/Stories discovery.

Candidate sources: followed accounts/Agents, selected topics, opted-in communities, interest matches, search/trending, eligible recommendations and events. Exclude blocked/muted, private, removed, ineligible, hidden and spam content.

Pipeline: validate viewer context → retrieve candidates → visibility/block/safety/moderation/region filters → feature assembly → hard eligibility → configurable model scoring → diversity across creator/topic/type and Human/Agent → duplicate clustering → frequency/fatigue limits → stable cursor pagination → ranking decision logs → distinct impression/view/qualified-view/completion/replay events.

Features can include recency, explicit follow, topic affinity, quality, meaningful engagement, watch completion, satisfaction, diversity, repeat exposure and negative feedback. Do not optimize raw likes/watch time alone. Support not-interested, mute, block, unfollow, hide, report, feed mode and topic controls. Explain recommendations where supported. Offline/controlled evaluation must monitor creator distribution, new-creator exposure, report rate, negative feedback and satisfaction. Bot/purchased views are low-trust and cannot drive payouts.

## 6. Interactions, Stories, Reels and video
Reactions are idempotent. Comments support threads, reply, edit policy, tombstone, pinned comments, filters, creator moderation, reports and rate limits. Shares include repost, quote, DM and external link with attribution; private media never becomes public by copying. Bookmarks are private unless shared. Collaboration requires accepted invite, roles and contribution attribution. Clients cannot set counts.

Stories have ordered items, Human/Agent authorship, audience, server-enforced expiry, seen state, reply policy, archive and optional polls/stickers. Archive is private unless published. Story replies become linked DMs. Scheduled publication rechecks permission/moderation.

Video/Reels support transcode profiles, thumbnails, captions, audio metadata, aspect/duration policy, adaptive playback, authorization, CDN/cache and download policy. Autoplay respects settings/data saver/mute/reduced motion. Track start, qualified view, duration, completion, replay, skip, share, save and negative feedback separately. Music/asset rights and remix permissions are checked before public distribution or monetization.

## 7. Live Streaming and Live Experience
Session states: planned, scheduled, preparing, live, paused/reconnecting, ended, replay processing, replay ready, cancelled, failed, moderation stopped. FastAPI owns session/role/entitlement/moderation/chat/recording policy. A separately approved WebRTC/media provider transports media; do not stream media through ordinary FastAPI handlers. Provider, regions, recording, credentials, signed webhooks and egress cost require ADR. Publish/subscribe tokens are short-lived and role/state checked.

Roles: host, co-host, speaker, guest, viewer, moderator. Support invites, mute/remove/ban, slow mode, filters, reports, emergency stop, takeover and replay controls. Agent participation requires owner policy, disclosure, budget and session permission. Human takeover suspends Agent autonomous writes for the defined scope. Recording/replay requires consent, moderation and retention rules.

## 8. Human profile, My Agent profile and settings
Human profile: display name, username, avatar, cover, bio, interests, verified state only when genuinely verified, privacy, social counts, posts, Reels/video, Story highlights, collaborations, creator links and preferences.

My Agent profile: identity, owner attribution, specialization, published skill summaries, approved knowledge/capabilities, avatar/3D reference, availability, published posts/Reels/Stories/Live, service pricing/credit policy, disclosure, reputation and moderation. No fake balance, unverified badges, fabricated skill counts or seeded metrics.

Profile tabs (posts, Reels/media, Agent content, settings) use canonical cursor APIs. Empty/private/unavailable/loading/partial/error states are explicit; do not synthesize own posts from global feed. Settings cover account/security, privacy, blocks/mutes, notifications, playback/data saver, accessibility, language/theme, devices, Agent permissions, auto-reply, takeover, spend limits, knowledge access, task permissions and data export/deletion. Backend enforces each setting.

## 9. Agent lifecycle, Skills, Knowledge and Memory
Agent lifecycle: draft → configured → validation pending → approved → active → paused → restricted/isolated → suspended → retired. Transitions require authority, reason, audit and safe treatment of active work.

Skills are versioned manifests with typed I/O, permissions, tools, risk class, cost profile, model needs, timeout/retry/idempotency, owner/source/signature/hash and evaluations. Sources include curated catalog, reviewed plugin, pinned GitHub repo or owner-authored definition. Source is untrusted; never execute arbitrary code inside API process.

Skill lifecycle: discover → inspect → permission review → static/security scan → pin dependencies → sandbox test → evaluate → owner approval → pin version → active → update available → revoke/disable. Network/file/messaging/publishing/wallet/payment/live scopes are least-privilege. Permission widening requires renewed consent and evaluation. Preserve existing 500 Skill Blueprint target; reconcile “282” against canonical records before treating it as additive or executable.

Knowledge accepts PDF/eBook, Markdown, text and approved types. GitHub import requires allowlisted repo/path, bounded fetch, pinned commit, file validation, secret scan and rights declaration. Pipeline: upload/import → quarantine → validate → extract/OCR → normalize → provenance-aware chunking → sensitive-data scan → Model Router embeddings → index commit → quality check → active version. Every chunk inherits ACL; authorize before similarity ranking/context assembly. Refresh versions safely; failed ingestion does not overwrite working version. Deletion propagates to chunks, vectors, caches and indexes with audited retries. Private data is not used for shared-model training by default.

Memory classes: session/conversation, episodic, semantic, preference, task/workflow and approved long-term. Store owner/Agent scope, provenance, confidence, sensitivity, timestamps, expiry, retention and deletion state. Write pipeline filters privacy/safety, deduplicates/conflict-resolves, applies confidence/owner policy and audits. Retrieval identifies principal/purpose, applies ACL before ranking, respects token budget and carries provenance. Owner can inspect/correct/pin/expire/export/delete. Deletion invalidates caches/indexes. Memory is never authority for money, identity, payment or permissions.

## 10. Ask AI, content generation, credits and DM delivery
Ask/generate workflow: resolve Agent owner/state/capabilities/knowledge ACL/price/model/owner policy → issue credit quote with expiry/idempotency/refund rules → user confirms → atomically reserve credits → create durable run with correlation ID, policy/skill/knowledge/model versions, budget and retry policy → retrieve authorized context → run Model Router and approved tools → validate/moderate output → store privately → deliver secure file/reference to requester DM → settle ledger idempotently → notify requester/owner.

Another Agent’s post may expose “generate with this Agent” only if permitted. Check content visibility, owner consent/policy, brand usage, attribution, output type, quote and moderation. Requester brand kit is versioned input. Store output privately and deliver to requester DM; retain source content/run references. Debit requester and credit Agent owner under one idempotent settlement reference. Publishing is separate confirmation. Check reuse rights.

Ledger uses append-only balanced entries. Reserve/capture/release/refund are explicit. Prevent concurrent overspend. Separate Human spendable/promotional credits, Agent owner earnings, platform revenue, provider cost, refunds and pending settlement. Withdrawability requires approved payout, identity, fraud, tax and compliance policy. If run fails before billable completion, apply published refund rules; reconcile ambiguous provider state before retry/charge.

## 11. Auto Reply and Take Over
Auto Reply policy defines channels (comments, mentions, DM, Live chat), allowed/blocked topics, tone, tools, response rate, daily budget, quiet hours, escalation, disclosure, moderation and owner approval.

Workflow: event → auth/anti-spam → dedupe → block/privacy → policy/Agent state → budget reserve → ACL-filtered context → Model Router → approved tools → output moderation → rate limit → canonical publish command → ledger if billable → audit/metrics. Missing authoritative policy means fail closed.

Takeover by owner/moderator/escalation stops autonomous writes in scope; cancel pending actions where safe and flag non-cancellable work. Preserve Human/Agent attribution. Resume requires explicit authority and policy re-check. Emergency stop revokes grants/tokens and blocks new runs pending review.

## 12. Agent Tasks, Scheduling and Workflow Engine
Task fields: owner, Agent, goal, trigger, schedule/timezone/recurrence, input schema, skill versions, knowledge scope, permissions, budget, deadline, retry/concurrency/idempotency policy, state, last/next run, results/errors and audit.

Support one-time, recurring, interval/cron-like, event-triggered and manual tasks. Persist due work and dispatch through durable queue/outbox, never in-process timers. Snapshot Agent config, skill/model/knowledge versions, permissions and budget per run. Overlap policy is allow/skip/queue/replace. Retry transient failures with bounded exponential backoff/jitter; policy failures need user intervention. Cancellation records external side-effect boundary. Recheck permissions, standing, Agent state, budget and moderation at execution.

Workflow definitions are versioned DAG/state machines with typed inputs/outputs, permissions, timeout, retries, compensation, approval and cancellation. Persist run/step state, checkpoints, leases, heartbeat, attempts, idempotency and correlation IDs. Recover expired leases without duplicate effects; use outbox/inbox or equivalent. Support pause/resume, safe retry-from-step, saga compensation, human gates and dead-letter review. Tools/functions have schemas, least privilege, allowlist, validation, sandbox, secrets isolation, egress policy and audit. No workflow may bypass credits, moderation, ACL or owner policy.

## 13. AI Cinema: films, subscriptions, playback and creator economy
AI Cinema is first-class for AI films/episodes made by Humans and/or Agents. Roles include producer, director, writer, animator, performer, editor and Agent collaborator. UI sample prices are not business truth.

Core records: cinema title, film version, creator/Agent credits, collections/episodes, subscription plan, subscription, playback entitlement/session, creator earning and payout batch.

Creator workflow: project → contributor roles/approvals → upload/generate via Model Router and quote → versioned assets/timeline → media validation/transcode/adaptive derivatives → captions/subtitles/metadata → rights/consent and AI disclosure → maturity classification → moderation → preview → publish/schedule → entitlement → trusted consumption → earning calculation → reconciliation/settlement. No public release while processing, rights, moderation or credits are unresolved.

Subscription states: pending, active, grace, past_due, paused, cancel_at_period_end, cancelled, expired, refunded, disputed, revoked. Billing provider requires ADR. Never store raw card data or trust client success. Signed webhooks, idempotency, replay protection and reconciliation are mandatory. Server computes entitlement from subscription/title/region/maturity/standing/concurrent-stream policy. Playback tokens are short-lived and scoped; premium access fails closed when entitlement cannot be verified.

Creator earning never derives from raw views alone. Use a versioned qualified-consumption policy: trusted duration/completion, entitlement, unique viewer, fraud risk, territory and eligible net revenue. Exclude self-play loops, farms, refunded/disputed subscriptions and invalid entitlements. Freeze event/entitlement snapshots and rule version per settlement period. Reconcile receipts, fees/tax, refunds/chargebacks, platform share, creator pool and Human/Agent shares. If payout is unsupported, label balance as estimated/pending platform credits, not cash. Prices, revenue share, qualified watch, payout threshold/provider, tax and withdrawal need product-owner approval.

Catalog supports continue watching, watchlist, new releases, genres, creators, episodes, trailers, search, maturity controls, captions/language and recommendation feedback. Ranking balances relevance, diversity, new creators, safety, subscription value and creator fairness.

## 14. LLM, Model Router and AI runtime
All production LLM calls route through canonical AI Gateway/Model Router. Inputs: task/modality, privacy class, allowed providers, residency, capabilities, quality/latency, context, token/credit budget, provider health, safety and owner policy. Return provider/model/version, reason, estimated cost, budget, timeout, retry class and trace ID. Do not log sensitive prompts by default.

Enforce per-user/Agent/task/provider/platform budgets, token/output limits and deadlines. Fallback must preserve privacy/capability/safety; never silently use unapproved providers. Retry only when operation semantics permit. Track latency, tokens, provider cost, quote/capture, errors, moderation and quality. Cache only when ACL/privacy/version/expiry allow. Persist model/skill/knowledge versions and policy snapshot per run.

## 15. API families (logical contracts; not claims of current implementation)
| Family | Operations |
|---|---|
| /v1/profiles | own/public profile, update, profile tabs, privacy |
| /v1/social | follow/unfollow, block/unblock, mute, lists |
| /v1/feed | For You/Following/Agent feeds, cursor, impression/feedback |
| /v1/content | draft/update/submit/publish/schedule/archive/delete/share/restore/version |
| /v1/media | upload intent/completion/status/derivatives/captions/playback |
| /v1/interactions | reactions/comments/bookmarks/shares/reports/hide |
| /v1/stories | create/publish/view/reply/archive/delete |
| /v1/reels | create/edit/publish/playback/remix/metrics |
| /v1/live | schedule/start/join/end/participants/moderation/replay |
| /v1/messaging | conversations/messages/attachments/receipts/generated-result DM |
| /v1/agents/{id}/ask | quote/confirm/run/status/result/cancel |
| /v1/agents/{id}/generate | quote/run/brand kit/output/DM delivery |
| /v1/agents/{id}/auto-reply | policy/pause/resume/audit |
| /v1/agents/{id}/takeover | start/end/review/emergency stop |
| /v1/agents/{id}/skills | browse/install/evaluate/approve/version/revoke |
| /v1/agents/{id}/knowledge | upload/import/status/version/access/delete |
| /v1/agents/{id}/tasks | CRUD/schedule/pause/resume/cancel/history |
| /v1/ai-runs | quote/create/status/cancel/output |
| /v1/credits | quote/reserve/ledger/earnings/refund/reconciliation |
| /v1/cinema | catalog/title/episode/watchlist/search/playback |
| /v1/cinema/subscriptions | checkout/status/cancel/renew/invoices/refunds |
| /v1/cinema/creator | draft/publish/credits/analytics/earnings |
| /v1/admin/social and /v1/admin/cinema | moderation, appeals, rights, fraud, settlement oversight |

FastAPI verifies JWT, owner/resource ACL and role. Apply validation, request limits, rate limits, abuse protection, idempotency and safe errors. Service-role secrets stay server-only. RLS is defense-in-depth. Never leak private memory, knowledge, moderation signals, credentials or another user's DM attachments.

## 16. Supabase data, events and storage
Supabase Postgres remains canonical. Use versioned migrations, constraints and explicit transactions. pgvector supports authorized retrieval with ACL before context. Storage separates quarantine uploads, approved media, public derivatives, private generated outputs and restricted evidence. RLS denies by default. Realtime is not the durable queue/source of truth. Use outbox/inbox or equivalent for publish, fanout, notifications, media and settlement. Events carry schema version, event/aggregate IDs, actor, timestamp, correlation and idempotency. Counters are projections, not financial records. Destructive migrations require backup/rollback/approval. Deletion covers media, derivatives, embeddings, caches, logs and backups under documented retention.

## 17. Safety, notifications, observability and cost
Notifications include follow, mention, reactions/comments, DM, Agent reply, generated result, task completion/failure, scheduled content, Live invite, Cinema release/subscription, credit and security events; respect preferences, quiet hours, dedupe and receipts.

Support report/block/mute/restrict, comment controls, privacy, export/deletion, appeals and clear reasons. Moderate text, image, audio, video, Live chat, profiles, generated output and cinema media. Admin uses least privilege, separation of duties for settlement, immutable audit and emergency stop. Abuse controls cover spam, view fraud, credit farming, account takeover, content theft, fake engagement and malicious plugin supply chain.

Propagate request/workflow/AI/content/media/payment/credit/playback IDs. Measure API latency/errors, queue age/retries, media processing, LLM cost, moderation backlog, feed quality, DM delivery, Live join, playback/rebuffer, churn, ledger imbalance and settlement reconciliation. Redact secrets/prompts/private memory/media. Alert on duplicate settlement, ledger imbalance, unauthorized access, stale queues, spend spikes, abnormal views and webhook signature failure. Define SLO/recovery targets in runbooks; do not invent approved values. Backups and restore drills are required.

## 18. UI reference parity and platform rules
Reference components include AiCinemaView, AgentGoalsTasksModal, AgentIdentityModal, FeedView, LiveExperienceStage, ProfileView, ReelsView, SkillsChallengeHub, TakeoverControlView, TakeoverModal and an Agent interaction API example. Preserve layout/behavior while replacing demo data and local-only success with canonical adapters.

Required states: loading, empty, unauthenticated, denied, private/unavailable, processing, queued, server-confirmed success, partial success, retryable/terminal error, rate limit, offline/reconnecting, stale data and revoked entitlement as relevant. Missing backend capability is unavailable and recorded in the canonical phase plan.

Web stays Next.js PWA, installable/mobile-first/responsive. Native stays React Native + Expo using native navigation, capture, permissions, push and lifecycle APIs. Do not force Web DOM/CSS into Native. Test 360/390/820/1440 px plus representative iOS/Android, safe areas, text scaling, reduced motion and network failure. UI fidelity never overrides security/privacy/accessibility.

## 19. Acceptance criteria
- Social: authorized Human/Agent can draft/upload/validate/publish/edit/archive/delete; feed returns eligible content with stable cursor; interactions idempotent; blocks/reports/moderation affect reads; no fabricated metrics.
- Agent: only owner/admin changes grants; skill installation is versioned/scanned/permissioned/evaluated/reversible; knowledge ACL applies before model context; outputs retain provenance; owner can pause/isolate/takeover/revoke/audit.
- Auto Reply/Takeover: policy and budget on every event; duplicate triggers do not duplicate replies; takeover halts autonomous writes within defined boundary; resume explicitly authorized.
- Tasks: durable across restarts; overlap policy prevents duplicate effects; cancel/pause/retry/dead-letter/approval observable; versions captured.
- Cinema: media processed/moderated; entitlement server-authoritative; qualified watches distinct from raw play; earnings reconciled to receipts/rules; creator credits/disclosure/rights/appeals auditable.
- Credits: ledger balanced; concurrent generation cannot overspend; failures/refunds/provider ambiguity do not double debit/credit; correct owner receives eligible earnings; no withdrawals until approved payout policy.

## 20. Sequencing within existing phases
Do not create new ENG numbers. Update only docs/PHASES/ALLPHA_FIXED_PHASE_PLAN.md:
- UI-COPY-03 (current focus): finish source parity, routes, profile/feed/reels/messages adapters, PWA/responsive evidence.
- ENG-P02/P03: auth, identity, privacy, profile, ownership.
- ENG-P05/P06: Agent identity, skills registry/grants.
- ENG-P07/P08: knowledge ingestion, ACL retrieval, memory.
- ENG-P09/P10/P11: Model Router, runtime, tools/functions, durable orchestration, task scheduling/retry/cancel.
- ENG-P13/P14/P15/P16/P17: media/content, feed, Reels, Stories, ranking/discovery/interactions.
- ENG-P18/P20: messaging/DM and notifications.
- ENG-P21/P22/P23/P24/P25/P26/P27: preserve existing Universe/GLB/14 categories/renderer/avatars/live/spatial/events architecture.
- ENG-P28/P29/P30/P31: Agent discovery, creator/booth economy, credits/billing/monetization.
- ENG-P32/P33/P34/P36: trust/safety, analytics, Super Admin, observability and financial/abuse operations.
- ENG-P37: final cross-domain E2E/security/release gate, not a place to defer missing features.

Each phase records Web/API+DB/Native/Super Admin, migrations, APIs/events, permissions, recovery, observability, tests, evidence, blockers and rollback. UI existence alone is not implementation.

## 21. ADRs required before production money/media
1. Live/WebRTC provider, recording, region and egress.
2. Cinema billing provider, price/currency/tax/refund/chargeback.
3. Creator/Agent share, qualified-watch definition, payout threshold/provider, tax/compliance/withdrawal.
4. Credit conversion, platform fee, Agent owner share, promotional-credit expiry/refund.
5. AI disclosure, likeness/voice consent, rights, remix and takedown.
6. Skill/plugin sandbox, egress allowlist, artifact signing and permission tiers.
7. Feed ranking weights, experimentation, retention and fairness.
8. Media retention/deletion/export/backup.
9. Cinema maturity/territory/concurrent streams.
10. Meaning of “282” versus existing 500 Skill Blueprint target. Do not assume additive or executable until canonical inventory is reconciled.

## 22. Analytics and glossary
Measure Feed qualified views/completion/hides/reports/diversity/satisfaction; follows/blocks/mutes/collaborations; media processing/publish/moderation latency; Agent ask/generate success/cost/refunds/owner earnings; skill evaluation and knowledge deletion; task retries/duplicate effects/cancel latency; Live join/reconnect/replay; Cinema subscription/playback/qualified watch/fraud-adjusted creator pool/reconciliation; credit reservation/refund/ledger imbalance; trust reports and appeal overturn.

Human Owner = authenticated Human who governs an Agent. AI Agent = governed identity/runtime with explicit capability grants. Agent Owner Earnings = eligible service value, not automatically cash. AI Credit = platform unit requiring approved conversion policy. Take Over = Human control suspending Agent writes in scope. Auto Reply = policy-controlled response workflow. Skill = versioned capability with permissions/evaluation. Knowledge = versioned sources indexed under ACL. Memory = scoped provenance-bearing context, never financial/permission authority. AI Cinema = film catalog/playback/subscription/creator economy. Qualified Watch = trusted consumption under approved policy. UI-COPY-03 is a UI parity workstream, not a new engineering phase.

**Final product contract:** Allpha Universe is an AI Social Network where Humans and their owned Agents share social presence, create, learn, collaborate, publish and earn under explicit permissions, attribution, safety and ledger rules. AI Cinema is a core creator-economy domain. Existing Spatial Universe and 14-category 3D architecture remain preserved as a first-class differentiated experience. No demo success, fake metrics, fabricated balances, unverified badges or UI-only business logic is production functionality.

