# Skills Layer Augmentation — Design Addendum

**Version:** 3.1-skills
**Date:** March 8, 2026
**Status:** Proposed Enhancement to v3 Design
**Author:** ConfigZ Project Team
**Prerequisite:** Self-Sustaining Parser Validation & Update System v3.0

---

## Executive Summary

This document proposes augmenting the v3 multi-agent architecture with a **Skills Layer** — modular, file-based instruction sets that agents read at task time and rewrite based on feedback. The core insight is that our agents already contain implicit skills (scraper CSS selectors, type inference rules, prompt templates, priority weights) embedded in Python code. Making these explicit, versionable, and self-modifiable unlocks the "Continuous Learning" capability listed in v3 as a Phase 4 goal, and brings it forward into every phase.

### What Is a Skill?

A Skill is a folder containing:
- A **SKILL.md** file with instructions the agent reads at task time (the "how")
- **Reference files** with domain knowledge loaded on-demand (the "what")
- **Eval files** with test cases for self-improvement (the "proof")

Skills are Git-versioned files — not code, not databases, not services. The agent reads them, uses them, evaluates its own output against them, and proposes rewrites when it detects gaps.

### Why Skills?

| Problem Today | How Skills Fix It |
|--------------|-------------------|
| Scraper CSS selectors are Python code — a vendor doc format change requires code change + deploy | Selectors live in a `.md` reference file — agent can rewrite them and submit a PR |
| Prompt templates are hardcoded f-strings — tuning requires code change | Prompts live in skill reference files — agent can A/B test and evolve them |
| Priority weights are an inline formula — adjusting requires code change | Weights live in `priority-weights.md` — agent adjusts based on human feedback |
| False positives require manual investigation | `false-positive-catalog.md` grows automatically from reviewer feedback |
| "Continuous Learning" is a Phase 4 goal with no concrete mechanism | Every agent has an evaluate-diagnose-rewrite loop from Phase 1 |

### What Does NOT Change

Everything from v3 not related to skills carries forward unchanged:

- CLI-Doc-First principle (vendor CLI command references as single source of truth)
- MRO-aware parser analysis with bidirectional cross-reference
- Library-agnostic pattern detection (ciscoconfparse2, TTP, regex)
- 6 gap types including `parsing_error` and `dead_field`
- Generate-validate-fix loop (3 attempts, 90%+ success target)
- Semantic validation against vendor examples
- regexploit ReDoS detection + config corpus testing
- Durable workflows with checkpoints
- LLM usage tracking
- Earn-the-complexity infrastructure strategy
- All human-in-the-loop touchpoints
- Config corpus lifecycle and golden test authorship model

---

## Table of Contents

1. [Skills Architecture](#skills-architecture)
2. [Where Skills Already Exist Implicitly](#where-skills-already-exist-implicitly)
3. [Skills Per Agent — Detailed Design](#skills-per-agent--detailed-design)
4. [New Component: Skill Evolution Agent](#new-component-skill-evolution-agent)
5. [Revised System Architecture](#revised-system-architecture)
6. [Implementation Strategy](#implementation-strategy)
7. [Data Models — Additions](#data-models--additions)
8. [Risk Analysis — Skills-Specific](#risk-analysis--skills-specific)
9. [Updated Success Metrics](#updated-success-metrics)
10. [Decision Record](#decision-record)

---

## Skills Architecture

### Skill Folder Structure

```
skill-name/
├── SKILL.md                  ← Agent instructions (read at task time)
├── references/               ← Domain knowledge (loaded on-demand)
│   ├── vendor-specific.md    ← Per-vendor/OS reference
│   └── shared-concepts.md    ← Cross-vendor patterns
├── evals/
│   └── evals.json            ← Test cases with assertions
├── scripts/                  ← Deterministic helpers (optional)
└── history/                  ← Previous SKILL.md versions (auto-maintained)
```

### Three-Level Progressive Loading

Skills use progressive disclosure to keep LLM context windows lean. This mirrors our existing pattern where vendor-specific scrapers load on-demand — it formalizes that pattern across all agents.

| Level | What Loads | When | Size Target |
|-------|-----------|------|-------------|
| **L1: Metadata** | Skill name + description (YAML frontmatter) | Always available to agent | ~100 words |
| **L2: SKILL.md body** | Full instructions for this task type | When skill triggers on a task | <500 lines |
| **L3: References** | Vendor-specific docs, syntax guides, examples | On-demand based on vendor/OS in current task | Unlimited |

**Why this matters:** A single vendor-doc-extraction skill can cover Cisco IOS, NX-OS, IOS-XR, and Arista EOS without loading all four vendor reference files. The agent reads SKILL.md (L2) and then loads only `arista-eos-selectors.md` (L3) when processing an Arista task.

### Self-Improvement Loop

Each skill includes an `evals/` directory. The improvement cycle:

```
Execute task using skill
    |
    v
Compare output to eval assertions
    |
    v
[All pass?] ──Yes──> Done (skill is healthy)
    |
    No
    v
Diagnose: which instruction or reference caused the miss?
    |
    v
Rewrite: update SKILL.md or specific reference file
    |
    v
Re-run evals: verify improvement, check for regression
    |
    v
Version: commit updated skill to Git, create PR
    |
    v
Human reviews skill-change PR
```

> **Key:** This generalizes the generate-validate-fix loop that already exists in the Code Generator. The Skills Layer applies the same pattern to ALL agents — not just code generation.

### Skill File Conventions

**SKILL.md format:**

```markdown
---
name: skill-identifier
description: What this skill does. Human-readable summary.
version: 1.0.0
owner_agent: doc-monitor | parser-analyzer | gap-analyzer | code-generator | validator | orchestrator
triggers:
  task_types: [extract_attributes, full_monitor_cycle]  # which task types activate this skill
  requires:
    context_has: [html_content, vendor, os_type]         # TaskContext fields that must be present
    context_lacks: []                                     # TaskContext fields that must be absent (optional)
  priority: 10                                            # higher = checked first when multiple skills match
---

## Purpose
What this skill enables the agent to do.

## When to Use
Specific triggers and conditions.

## Instructions
Step-by-step instructions in imperative form.

## References
Which reference files to load and when.

## Eval Criteria
What "good output" looks like for this skill.
```

**Reference file format:**

```markdown
---
vendor: arista
os_type: eos
last_validated: 2026-03-01
confidence: 0.92
---

## CSS Selectors for Attribute Extraction
...

## Fallback XPath Expressions
...

## Known Edge Cases
...
```

**Eval file format:**

```json
{
  "skill_name": "vendor-doc-extraction",
  "evals": [
    {
      "id": 1,
      "prompt": "Extract BGP attributes from Arista EOS 4.32 command reference page",
      "input_files": ["test_data/arista_eos_bgp_4.32.html"],
      "expected_output": "AttributeCatalog with >=15 attributes including remote-as, update-source, soft-reconfiguration",
      "assertions": [
        "output.attributes contains 'remote-as'",
        "output.attributes contains 'soft-reconfiguration inbound'",
        "output.extraction_method == 'rule_based'",
        "output.extraction_confidence >= 0.85",
        "len(output.attributes) >= 15"
      ]
    }
  ]
}
```

---

## Where Skills Already Exist Implicitly

Before designing new skills, it's worth recognizing that domain knowledge is already embedded in our agents. This table maps implicit skills to the proposed explicit skill files:

| Agent | Implicit Skill (today) | Where It Lives Now | Proposed Skill File |
|-------|----------------------|-------------------|-------------------|
| Doc Monitor | CSS/XPath selector rules per vendor | `CiscoCLIDocScraper` class methods | `vendor-doc-extraction/references/{vendor}-selectors.md` |
| Doc Monitor | Version string parsing patterns | `CiscoIOSXEVersionParser`, etc. | `version-detection/references/{vendor}-version-patterns.md` |
| Doc Monitor | LLM fallback extraction prompts | Hardcoded prompt strings | `vendor-doc-extraction/references/llm-extraction-prompt.md` |
| Parser Analyzer | Library detection patterns | Pattern matching in AST walker | `parsing-pattern-recognition/references/{library}-patterns.md` |
| Gap Analyzer | Priority scoring weights | Inline formula in code | `gap-detection-rules/references/priority-weights.md` |
| Gap Analyzer | Attribute normalization rules | `lowercase + collapse whitespace` logic | `gap-detection-rules/references/normalization-rules.md` |
| Code Generator | CLI type → Python type mappings | Lookup dict in Python | `parser-code-generation/references/cli-type-mappings.md` |
| Code Generator | Code gen prompt templates | Hardcoded f-strings | `parser-code-generation/references/prompt-templates/*.md` |
| Validator | Quality gate thresholds | Sequential function calls | `validation-pipeline/references/gate-thresholds.md` |
| Orchestrator | Workflow step ordering + retry policy | Hardcoded step sequence | `workflow-orchestration/references/escalation-rules.md` |

**The maintenance problem:** When any of these change (a vendor redesigns their docs, a new CLI type pattern appears, a prompt needs tuning), an engineer must locate the right Python file, modify it, test it, and deploy it. This is the maintenance burden that the 20% annual allocation accounts for.

**The skills solution:** Move this knowledge into files the agents themselves can read, evaluate, and propose updates to. Engineers review skill-change PRs instead of writing the changes.

---

## Skills Per Agent — Detailed Design

### 1. Documentation Monitor Agent

This agent benefits the **most** from skills because vendor documentation format changes are the **#1 operational risk** in the v3 design. Today, a format change requires a code change. With skills, the agent can detect a scraper failure and propose fixes to its own extraction rules.

#### Skill: `vendor-doc-extraction`

```
vendor-doc-extraction/
├── SKILL.md                           ← Extraction pipeline instructions
├── references/
│   ├── cisco-ios-selectors.md         ← CSS/XPath rules for Cisco IOS/IOS-XE docs
│   ├── cisco-iosxr-selectors.md       ← CSS/XPath rules for IOS-XR docs
│   ├── cisco-nxos-selectors.md        ← CSS/XPath rules for NX-OS docs
│   ├── arista-eos-selectors.md        ← CSS/XPath rules for Arista EOS docs
│   ├── llm-extraction-prompt.md       ← Prompt template for Tier 2 LLM fallback
│   └── extraction-validation-rules.md ← What makes a valid extraction (>=3 attrs, etc.)
├── evals/
│   └── evals.json                     ← Known pages with expected AttributeCatalogs
└── history/
    └── arista-eos-selectors.md.v1     ← Previous version for rollback
```

**What SKILL.md contains:**

Step-by-step instructions for the extraction pipeline:
1. Identify vendor and OS type from the URL/page content
2. Load the appropriate vendor selectors reference file
3. Apply CSS selectors to extract Syntax Description tables
4. Validate extraction (name present, type parseable, >=3 attributes)
5. If validation fails → load `llm-extraction-prompt.md` and use Tier 2
6. Tag result with `extraction_method` and `extraction_confidence`
7. If LLM fallback produced better results than rules → flag selectors file for review

**What vendor selector reference files contain:**

```markdown
---
vendor: arista
os_type: eos
last_validated: 2026-03-01
pages_tested: 12
success_rate: 0.92
---

## Primary CSS Selectors

### Syntax Description Table
- Table selector: `table.command-syntax` or `div.syntax-description table`
- Parameter name column: `td:first-child code`
- Description column: `td:nth-child(2)`
- Type/range column: `td:nth-child(3)` (may not exist on all pages)

### Command Mode Section
- Selector: `h3:contains("Command Mode") + p` or `div.command-mode`
- Fallback: look for text matching "Router configuration mode" pattern

### Version Introduced
- Selector: `div.version-info` or `span.introduced-in`
- Pattern: "Introduced in EOS X.Y.Z"

## Fallback XPath Expressions
(used when CSS selectors return empty)
- `//table[contains(@class, 'syntax')]//tr`
- `//div[contains(text(), 'Syntax Description')]/following-sibling::table[1]`

## Known Edge Cases
- Some EOS pages use `div.content-table` instead of `table.command-syntax`
- BGP address-family pages nest parameters inside expandable sections
- Deprecated commands may lack the version-introduced field
```

**Self-improvement scenario: Arista redesigns their doc pages**

| Step | Today (v3) | With Skills |
|------|-----------|-------------|
| 1. Detection | Scraper fails, success rate drops | Same — scraper health monitoring triggers |
| 2. Fallback | LLM extraction activates (already in v3) | Same — LLM fallback produces correct output |
| 3. Diagnosis | Engineer receives alert, investigates manually | Agent compares LLM output vs rule-based output, identifies which selectors failed |
| 4. Fix | Engineer rewrites CSS selectors in Python, tests, deploys | Agent proposes new selectors in `arista-eos-selectors.md`, runs evals to verify |
| 5. Review | N/A (was a code deploy) | Engineer reviews skill-change PR (smaller, easier to review than code changes) |
| 6. Time | Multi-day turnaround | Hours (LLM fallback covers gap while skill-change PR is reviewed) |

#### Skill: `version-detection`

```
version-detection/
├── SKILL.md                           ← How to parse vendor version strings
├── references/
│   ├── cisco-iosxe-versions.md        ← Pattern: 17.09.04a → (17, 9, 4, 'a')
│   ├── cisco-iosxr-versions.md        ← Pattern: 7.11.1 → (7, 11, 1)
│   ├── cisco-nxos-versions.md         ← Pattern: 10.4(3) → (10, 4, 3)
│   ├── arista-eos-versions.md         ← Pattern: 4.32.2.1F → (4, 32, 2, 1, 'F')
│   └── cisco-ios-versions.md          ← Pattern: 15.9(3)M7 → (15, 9, 3, 'M7')
└── evals/
    └── evals.json                     ← Version strings with expected parse results
```

**Self-improvement scenario:** A vendor introduces a new versioning scheme (e.g., Arista moves from `4.x` to `5.0.0`). The agent encounters an unparseable version string, adds the new pattern to the reference file, and submits a PR.

---

### 2. Parser & Model Analyzer Agent

This agent performs AST analysis and MRO walking — tasks that are more algorithmic than knowledge-driven. The skill here is about recognizing parsing patterns across different libraries.

#### Skill: `parsing-pattern-recognition`

```
parsing-pattern-recognition/
├── SKILL.md                           ← How to identify parsing patterns in code
├── references/
│   ├── ciscoconfparse2-patterns.md    ← re_search_children, re_match_iter_typed
│   ├── ttp-patterns.md               ← TTP template detection
│   ├── textfsm-patterns.md           ← TextFSM template detection
│   ├── regex-stdlib-patterns.md      ← stdlib re module patterns
│   └── string-ops-patterns.md        ← Plain string operations (split, startswith)
└── evals/
    └── evals.json                     ← Parser files with expected pattern detection results
```

**What each reference file contains:**

```markdown
---
library: ciscoconfparse2
import_signatures: ["from ciscoconfparse2", "import ciscoconfparse2"]
last_validated: 2026-03-01
---

## Detection Signatures
- Import: `from ciscoconfparse2 import CiscoConfParse`
- Constructor: `CiscoConfParse(config_text)` or `CiscoConfParse(filename)`
- Key methods that indicate parsing:
  - `find_objects()` → find config lines matching pattern
  - `re_search_children()` → search child lines with regex
  - `re_match_iter_typed()` → extract typed values from matches

## Attribute Extraction Patterns
When a ciscoconfparse2 method is found, the extracted attribute is typically:
- The regex capture group name in the pattern argument
- The dict key in the assignment target: `result['neighbor'] = match.group(1)`

## Known Limitations
- Does not detect dynamic method construction (e.g., `getattr(parser, method_name)()`)
- Template-based usage via config files not detectable from AST alone
```

**Self-improvement scenario:** An engineer introduces `ntc-templates` or `genie` as a new parsing library. The agent initially fails to detect it. After the miss is identified in eval, the agent creates a new `ntc-templates-patterns.md` reference file and updates SKILL.md to include it in the detection pipeline.

---

### 3. Gap Analysis Agent

The Gap Analyzer benefits from skills in two areas: **priority scoring** and **false positive suppression**. Both are knowledge that evolves over time based on human feedback.

#### Skill: `gap-detection-rules`

```
gap-detection-rules/
├── SKILL.md                           ← Comparison methodology + scoring instructions
├── references/
│   ├── normalization-rules.md         ← How to normalize attribute names for comparison
│   ├── priority-weights.md            ← Scoring formula + per-protocol weights
│   ├── false-positive-catalog.md      ← Known non-gaps to suppress
│   └── gap-type-definitions.md        ← The 6 gap types with identification criteria
├── evals/
│   └── evals.json                     ← Known gap/non-gap pairs for validation
└── history/
    ├── priority-weights.md.v1         ← Previous weights for rollback
    └── false-positive-catalog.md.v3   ← Previous FP catalog version
```

**`priority-weights.md` — currently an inline formula, now a tunable file:**

```markdown
---
last_tuned: 2026-03-01
tuned_by: skill-evolution-agent
tuning_basis: 47 merged PRs, 12 rejected gaps
---

## Scoring Formula

Score (0-10) = severity_weight + protocol_weight + gap_type_weight + breaking_bonus

Capped at 10.0. Gaps with score >= 7.0 eligible for auto-update code generation.

## Severity Weights
| Severity | Weight | Notes |
|----------|--------|-------|
| critical | 4.0 | Parser produces wrong output |
| high     | 3.0 | Missing commonly-used attribute |
| medium   | 2.0 | Missing rarely-used attribute |
| low      | 1.0 | Cosmetic or style mismatch |

## Protocol Weights
| Protocol | Weight | Rationale |
|----------|--------|-----------|
| bgp      | 3.0  | Most complex, most customer-impacting |
| ospf     | 2.5  | High usage, moderate complexity |
| vrf      | 2.5  | Foundational for multi-tenancy |
| vxlan    | 2.0  | Growing adoption |
| evpn     | 2.0  | Growing adoption |
| interface| 2.0  | Foundational but simpler |
| route_map| 2.0  | Policy control, moderate complexity |
| acl      | 1.5  | Well-established, fewer changes |

## Gap Type Weights
| Gap Type | Weight | Rationale |
|----------|--------|-----------|
| parsing_error      | 4.0 | Actively wrong > missing |
| missing_protocol   | 3.5 | Entire protocol not covered |
| syntax_mismatch    | 3.0 | Wrong CLI syntax used |
| missing_attribute  | 2.0 | Single attribute not captured |
| version_gap        | 1.5 | New version, unknown impact |
| dead_field         | 1.0 | Cleanup, not functional |

## Breaking Change Bonus
+2.0 if the gap involves a breaking change to existing behavior.
```

**`false-positive-catalog.md` — grows from human feedback:**

```markdown
---
entries: 23
last_updated: 2026-03-07
growth_source: CodeReviewFeedback where outcome == 'rejected' and reason == 'not_a_real_gap'
---

## Suppressed Attributes

These attributes appear in vendor CLI docs but are intentionally not parsed. Each entry includes the reason for suppression.

### Arista EOS - BGP
| Attribute | Reason | Added By | Date |
|-----------|--------|----------|------|
| `bgp trace` | Debug-only command, not in running-config | reviewer:jsmith | 2026-02-15 |
| `neighbor X shutdown` | Handled by interface-level shutdown detection | reviewer:alee | 2026-02-20 |

### Cisco IOS-XE - OSPF
| Attribute | Reason | Added By | Date |
|-----------|--------|----------|------|
| `log-adjacency-changes` | Default behavior, not persisted in config | reviewer:jsmith | 2026-03-01 |
```

**Self-improvement triggers:**

1. **Human rejects a gap as false positive** → Orchestrator routes `CodeReviewFeedback` to this skill → agent appends to `false-positive-catalog.md`
2. **Human consistently overrides priority scores** → Orchestrator routes feedback → agent adjusts weights in `priority-weights.md`
3. **New gap type pattern emerges** → agent proposes update to `gap-type-definitions.md`

---

### 4. Code Generator Agent

This is where skills have the **highest ROI** because prompt templates and type mappings are the most frequently tuned components, and improvements directly impact the 90%+ success rate target.

#### Skill: `parser-code-generation`

```
parser-code-generation/
├── SKILL.md                           ← Code generation pipeline instructions
├── references/
│   ├── cli-type-mappings.md           ← CLI type → Python type table
│   ├── prompt-templates/
│   │   ├── model-update.md            ← Prompt for Pydantic model changes
│   │   ├── parser-update.md           ← Prompt for parser method changes
│   │   └── test-generation.md         ← Prompt for test generation
│   ├── coding-patterns/
│   │   ├── ciscoconfparse2-examples.md← Few-shot examples by library
│   │   ├── ttp-examples.md
│   │   └── regex-examples.md
│   └── common-mistakes.md            ← Patterns that caused failures (learned)
├── evals/
│   └── evals.json                     ← Known gaps with expected code output
└── history/
    └── prompt-templates/              ← Previous prompt versions for A/B comparison
```

**`cli-type-mappings.md` — the type inference table as a learnable file:**

```markdown
---
last_updated: 2026-03-05
entries: 14
auto_extended: true
---

## CLI Type → Python Type Mappings

These mappings are used when generating Pydantic model fields from CLI documentation type descriptions.

| CLI Doc Type Pattern | Python Type | Pydantic Import | Example CLI Syntax |
|---------------------|-------------|-----------------|-------------------|
| `INTEGER`, `<1-N>` | `int` | — | `remote-as <1-4294967295>` |
| `WORD`, `LINE` | `str` | — | `description LINE` |
| `A.B.C.D` | `IPv4Address` | `from ipaddress import IPv4Address` | `neighbor A.B.C.D` |
| `X:X:X::X` | `IPv6Address` | `from ipaddress import IPv6Address` | `neighbor X:X:X::X` |
| `A.B.C.D/M` | `IPv4Network` | `from ipaddress import IPv4Network` | `network A.B.C.D/M` |
| `X:X:X::X/M` | `IPv6Network` | `from ipaddress import IPv6Network` | `network X:X:X::X/M` |
| `HH:MM:SS` | `str` | — | `timers HH:MM:SS` |
| `H.H.H` | `str` | — | `mac-address H.H.H` |
| `AA:NN` | `str` | — | `route-target AA:NN` |
| (keyword only, no arg) | `bool` | — | `soft-reconfiguration inbound` |
| `{opt1 \| opt2}` | `Literal["opt1", "opt2"]` | `from typing import Literal` | `mode {active \| passive}` |
| `<1-N>` with range | `conint(ge=1, le=N)` | `from pydantic import conint` | `keepalive <0-65535>` |

## Extension Rules

When a CLI type pattern is encountered that doesn't match any row above:
1. Log the unknown pattern with the source URL and context
2. Attempt inference: does it look like an IP? A number? A string?
3. Use `str` as the safe fallback
4. After successful code generation and validation, add the new mapping here
```

**`common-mistakes.md` — a learned file that grows from failures:**

```markdown
---
entries: 8
last_updated: 2026-03-06
source: CodeReviewFeedback + refinement loop failures
---

## Mistakes to Avoid When Generating Parser Code

### 1. Regex with unescaped dots in IP patterns
**Wrong:** `re.search(r'neighbor (\d+.\d+.\d+.\d+)', line)`
**Right:** `re.search(r'neighbor (\d+\.\d+\.\d+\.\d+)', line)`
**Source:** Refinement failure on gap-42, 2026-02-28

### 2. Missing Optional[] for attributes that may not appear
**Wrong:** `remote_as: int`
**Right:** `remote_as: Optional[int] = None`
**When:** Attribute is not mandatory in CLI config
**Source:** PR review feedback, reviewer:jsmith, 2026-03-01

### 3. Using 'vrf definition' syntax for Arista EOS
**Wrong:** `re.search(r'^vrf definition (\S+)', line)` (Cisco syntax)
**Right:** `re.search(r'^vrf instance (\S+)', line)` (EOS syntax)
**When:** Generating EOS parser for VRF-related attributes
**Source:** Semantic validation failure against EOS config corpus, 2026-02-20
```

**Self-improvement triggers:**

1. **Refinement loop failure** → error pattern added to `common-mistakes.md`
2. **Reviewer heavily edits generated code** → coding pattern updated in relevant `coding-patterns/*.md`
3. **New CLI type encountered** → `cli-type-mappings.md` extended
4. **First-attempt success rate drops** → agent A/B tests prompt variations and updates `prompt-templates/*.md`

#### Skill: `code-style-conventions`

A smaller, cross-cutting skill that encodes team coding conventions:

```
code-style-conventions/
├── SKILL.md                           ← Naming, imports, docstring conventions
└── references/
    ├── parser-conventions.md          ← parse_bgp not parseBgp, etc.
    ├── model-conventions.md           ← Pydantic model patterns
    └── test-conventions.md            ← Test file naming, fixture patterns
```

This skill is referenced by the Code Generator to ensure generated code matches the codebase style without relying solely on few-shot examples.

---

### 5. Validation & Testing Agent

#### Skill: `validation-pipeline`

```
validation-pipeline/
├── SKILL.md                           ← Quality gate sequence + pass/fail criteria
├── references/
│   ├── gate-thresholds.md             ← Configurable thresholds per gate
│   ├── golden-test-patterns.md        ← How to write and maintain golden tests
│   └── regex-safety-rules.md          ← ReDoS patterns beyond regexploit
└── evals/
    └── evals.json                     ← Known-good and known-bad code samples
```

**`gate-thresholds.md` — tunable per vendor/protocol:**

```markdown
---
last_tuned: 2026-03-01
---

## Quality Gate Thresholds

### Default Thresholds
| Gate | Pass Criteria |
|------|--------------|
| 1. Syntax | `ast.parse()` succeeds |
| 2. Type Check | mypy exits with 0 errors |
| 3. Lint | ruff reports 0 errors (warnings OK) |
| 4. Security | bandit reports 0 high-severity issues |
| 5. ReDoS | regexploit reports 0 vulnerable patterns |
| 6. Unit Tests | pytest passes all generated tests |
| 7. Semantic | >=80% of vendor example values match |
| 8. Regression | 0 existing tests broken, 0 corpus regressions |

### Per-Vendor Overrides
| Vendor/OS | Gate | Override | Reason |
|-----------|------|----------|--------|
| cisco_nxos | 3. Lint | Allow up to 2 warnings | NX-OS config syntax requires complex regex |
| * | 7. Semantic | >=60% for new protocols | Lower bar when golden tests are sparse |
```

**`golden-test-patterns.md` — teaches the agent what makes a good golden test:**

This reference helps the LLM-assisted golden test proposal feature (Phase 3+) by defining what makes a good test case:
- Should cover at least one mandatory and one optional attribute
- Should include at least one edge case (missing value, default behavior)
- Expected values should be specific (exact string/number), not vague
- Scope: 5-10 expected values per example, not exhaustive

---

### 6. Orchestrator Agent

#### Skill: `workflow-orchestration`

```
workflow-orchestration/
├── SKILL.md                           ← Workflow step ordering + coordination rules
├── references/
│   ├── operating-modes.md             ← Rules for Modes 1-4
│   ├── escalation-rules.md            ← When to escalate vs retry vs skip
│   ├── pr-template.md                 ← PR description format and required sections
│   └── feedback-routing.md            ← Which feedback types route to which skills
└── evals/
    └── evals.json                     ← Workflow scenarios with expected behavior
```

**`escalation-rules.md` — a learnable policy instead of hardcoded "3 attempts":**

```markdown
---
last_tuned: 2026-03-05
tuning_basis: 31 code generation outcomes
---

## Escalation Policy by Gap Type

| Gap Type | Max Retries | Auto-Escalate Condition | Notes |
|----------|-------------|------------------------|-------|
| parsing_error | 3 | Always after 3 failures | Active bugs need human eyes |
| missing_attribute | 3 | After 3 failures | Standard code gen task |
| syntax_mismatch | 2 | After 2 failures | Usually requires understanding vendor differences |
| missing_protocol | 1 | After 1 failure | Too complex for current code gen |
| dead_field | 0 | Always auto-generate | Simple removal, high success rate |
| version_gap | 2 | After 2 failures | Depends on scope of changes |

## Escalation Actions
- **Retry:** Feed errors back to Code Generator with updated context
- **Escalate:** Create draft PR with partial work + error log, assign to on-call engineer
- **Skip:** Log gap as "deferred", include in next gap report for human prioritization
```

**`feedback-routing.md` — maps feedback types to skills:**

```markdown
## Feedback Routing Table

| Feedback Source | Condition | Target Skill | Target File |
|----------------|-----------|-------------|-------------|
| `CodeReviewFeedback` | `outcome == 'rejected'`, `reason == 'not_a_real_gap'` | gap-detection-rules | false-positive-catalog.md |
| `CodeReviewFeedback` | `outcome == 'changes_requested'`, heavy edits | parser-code-generation | coding-patterns/*.md or common-mistakes.md |
| `GenerationOutcome` | `refinement_attempts >= 3`, `generated_successfully == false` | parser-code-generation | prompt-templates/*.md |
| `GenerationOutcome` | new CLI type encountered | parser-code-generation | cli-type-mappings.md |
| Scraper health metric | success_rate < 0.90 for vendor | vendor-doc-extraction | {vendor}-selectors.md |
| Scraper health metric | llm_fallback_rate > 0.30 | vendor-doc-extraction | {vendor}-selectors.md |
| Gap priority override | human changes score by > 2.0 | gap-detection-rules | priority-weights.md |
| Regression detected | post-merge regression | validation-pipeline | gate-thresholds.md |
```

---

## New Component: Skill Evolution Agent

### Purpose

A 7th agent that runs **outside** the normal pipeline. It consumes feedback from all sources and proposes skill file updates. This is the agent that makes the system self-sustaining.

The Skill Evolution Agent does not participate in daily workflows. It runs **after batches complete** (e.g., weekly or after N cycles) and examines accumulated outcomes.

### Architecture

```
Inputs:
  ├── CodeReviewFeedback (from merged/rejected PRs)
  ├── GenerationOutcome (success/failure/retry counts)
  ├── Scraper health metrics (per-vendor success rates)
  ├── LLMCallRecord data (prompt effectiveness, cost per gap)
  ├── False positive reports (from human gap reviews)
  └── Eval results (per-skill pass/fail rates)

Process:
  1. Aggregate feedback per skill
  2. Identify underperforming skills (below target metrics)
  3. Rank skills by improvement potential (most feedback, worst metrics)
  4. For the top-priority skill:
     a. Diagnose root cause (which reference file? which instruction?)
     b. Generate skill update (rewrite the specific file)
     c. Run skill evals to validate improvement
     d. Check for regression against other skills
  5. Create skill-update PR with before/after metrics

Output:
  ├── Updated skill files (SKILL.md, references, evals)
  ├── Skill performance report (before/after metrics)
  └── PR with diff + evidence
```

### Feedback Aggregation

The agent maintains a `skill_health` view per skill:

```python
class SkillHealthReport:
    """Aggregated health metrics for a single skill."""
    skill_name: str
    period: str  # "last_7_days", "last_30_days"
    eval_pass_rate: float  # % of eval assertions passing
    feedback_count: int  # total feedback items received
    negative_feedback_count: int  # rejections, heavy edits, overrides
    improvement_opportunities: list[str]  # specific files/sections to update
    last_updated: datetime
    last_self_updated: datetime  # when skill last rewrote itself
```

### Human Oversight

The Skill Evolution Agent follows the same human-in-the-loop model as the rest of the system:

| Decision | Auto? | Human Required? |
|----------|-------|-----------------|
| Aggregate feedback data | Yes | No |
| Identify underperforming skills | Yes | No |
| Generate skill update | Yes | No |
| Create skill-update PR | Yes | Review PR |
| Merge skill-update PR | No | Always |
| Add new eval cases | Yes | Review in PR |
| Modify eval assertions | No | Always (to prevent eval gaming) |

### Implementation Timing

The Skill Evolution Agent is a **Phase 4 component**. It requires accumulated feedback data from Phases 1-3 to operate meaningfully. However, the skill files themselves and the manual eval-run-rewrite loop should be introduced from Phase 0 onward (engineers can run evals manually during development).

---

## Revised System Architecture

### Updated Component Diagram

```
+-------------------------------------------------------------------+
|                    Orchestrator Agent                              |
|           (Workflow + Feedback Routing to Skills)                  |
+--------------------+----------------------------------------------+
                     |
     +---------------+--------------------------------------------+
     |                   Event Bus (Redis Streams)                |
     +--+------+----------+------------------+--------------+-----+
        |      |          |                  |              |
        v      v          v                  v              v
+--------+ +----------+ +---------+  +-----------+  +--------------+
| Doc    | | Parser & | | Gap     |  | Code      |  | Validation   |
| Monitor| | Model    | | Analysis|  | Generator |  | & Testing    |
| Agent  | | Analyzer | | Agent   |  | Agent     |  | Agent        |
+---+----+ +----+-----+ +----+---+  +-----+-----+  +------+------+
    |           |             |            |                |
    v           v             v            v                v
+--------+ +----------+ +---------+  +-----------+  +--------------+
|vendor- | |parsing-  | |gap-     |  |parser-    |  |validation-   |
|doc-    | |pattern-  | |detection|  |code-gen   |  |pipeline      |
|extract.| |recogn.   | |-rules   |  |skill      |  |skill         |
|skill   | |skill     | |skill    |  |           |  |              |
+---+----+ +----+-----+ +----+---+  +-----+-----+  +------+------+
    |           |             |            |                |
    +------+----+------+------+------+-----+--------+------+
           |           |             |              |
           v           v             v              v
    +------+----+ +----+------+ +---+-------+ +----+-----+
    | references | | evals/   | | history/  | | feedback |
    | *.md files | | evals.   | | rollback  | | routing  |
    |            | | json     | | versions  | |          |
    +------+-----+ +----+-----+ +----+------+ +----+----+
           |             |            |              |
           +------+------+------+-----+------+------+
                  |                          |
         +--------+--------+       +--------+--------+
         | Git: Skills Repo |       | Skill Evolution  |
         | (versioned files)|       | Agent (Phase 4)  |
         +-----------------+       +-----------------+
```

### What Changes vs. v3

| Aspect | v3 Current | v3.1 + Skills |
|--------|-----------|---------------|
| Scraper rules | Python class methods | Skill reference files (per-vendor `.md`) |
| Prompt templates | Hardcoded f-strings | Skill reference files (`prompt-templates/*.md`) |
| Type mappings | Python dict in code | `cli-type-mappings.md` in code-gen skill |
| Priority weights | Inline formula | `priority-weights.md` in gap-detection skill |
| False positive handling | Not specified until Phase 4 | `false-positive-catalog.md` from Phase 2 |
| Learning mechanism | Planned for Phase 4 generically | Concrete evaluate-diagnose-rewrite loop per agent |
| Maintenance model | Engineer edits Python code | Agent proposes skill changes, engineer reviews PRs |
| Rollback granularity | Full cycle rollback | Per-skill file rollback (git revert on single file) |
| Feedback consumption | Data captured but not consumed | Feedback routed to specific skills via defined routing table |

### What Stays the Same

Everything from v3 not listed above is unchanged. See the "What Does NOT Change" list in the Executive Summary.

---

## Implementation Strategy

### Phased Rollout

Following the v3 earn-the-complexity principle. Skill adoption is incremental — no big bang.

| v3 Phase | Skill Addition | Why at This Phase | Effort Added |
|----------|---------------|-------------------|-------------|
| **Phase 0** (PoC) | Extract Arista EOS scraper selectors into `arista-eos-selectors.md` | Zero-risk experiment: validate that extraction rules work as `.md` files. If this fails, we stop here. | ~2 days |
| **Phase 1** (Foundation) | `vendor-doc-extraction` skill + `version-detection` skill + `parsing-pattern-recognition` skill + SkillLoader utility | These agents benefit most from skills and have the clearest eval criteria (extraction accuracy, pattern detection accuracy) | ~1 week |
| **Phase 2** (Analysis) | `gap-detection-rules` skill with `priority-weights.md` and `false-positive-catalog.md` | Gap analysis is where feedback loops first become meaningful. Start accumulating false positive data from human reviews. | ~1 week |
| **Phase 3** (Code Gen) | `parser-code-generation` skill with prompt templates, type mappings, coding patterns, and `common-mistakes.md` | Highest ROI: prompt template evolution directly impacts 90%+ success rate target | ~1.5 weeks |
| **Phase 4** (Automation) | `workflow-orchestration` skill + `validation-pipeline` skill + **Skill Evolution Agent** | Introduce the meta-agent once there is enough accumulated feedback data (Phases 1-3) to drive meaningful self-improvement | ~2-3 weeks |

**Total additional effort across all phases:** ~6-8 weeks spread across 21-29 weeks of implementation.

### Infrastructure Additions

| Component | What It Is | How It Works | Infrastructure Cost |
|-----------|-----------|-------------|-------------------|
| `skills/` directory | Folder in repo | Git-versioned, same as code | None |
| `SkillRouter` | Python utility class | Evaluates skill trigger conditions against TaskContext. Declarative pattern matching, no LLM calls. | None (in-memory) |
| `SkillLoader` | Python utility class | Reads SKILL.md + references at task time with L1/L2/L3 progressive loading | None (in-memory) |
| `TaskContext` | Dataclass | Structured task descriptor passed from Orchestrator to agents. Agents populate it, SkillRouter evaluates it. | None |
| `EvalRunner` | Python utility class | Executes skill eval suites, reports results | None (uses existing pytest infra) |
| `FeedbackRouter` | Addition to Orchestrator | Maps feedback to skills per routing table | None (in-memory routing) |
| `SkillEvolutionAgent` | New agent (Phase 4) | Aggregates feedback, proposes skill updates | Additional LLM calls (~10-15% cost increase) |

No new databases. No new services. Skills are files in Git. Fully aligned with earn-the-complexity.

### Skill Routing & Loading Design

Skill selection is a **two-level problem**:

1. **Orchestrator → Agent:** Already solved in v3. The Orchestrator dispatches workflow steps to specific agents (Step 1 → Doc Monitor, Step 3 → Gap Analyzer, etc.).
2. **Agent → Skill:** The missing piece. When an agent owns multiple skills (e.g., Doc Monitor owns `vendor-doc-extraction` AND `version-detection`), how does it pick the right one for the current task?

#### Why This Matters

In v3, the Doc Monitor agent is a single class with two responsibilities baked in: extract attributes AND detect version changes. These are different tasks triggered by different conditions in the same workflow step. With skills, this becomes: which skill file do I read right now?

A naive approach (always load all skills) wastes context tokens. An LLM-based approach (ask the model to pick) adds latency and cost. We need something simpler.

#### Design: Declarative Trigger Conditions

Each skill declares **trigger conditions** in its YAML frontmatter. The agent's `SkillRouter` evaluates these conditions against the current `TaskContext` to select the right skill(s). No LLM call needed — this is pure pattern matching.

**SKILL.md frontmatter with trigger conditions:**

```yaml
---
name: vendor-doc-extraction
owner_agent: doc-monitor
triggers:
  task_types: [extract_attributes, scrape_docs, full_monitor_cycle]
  requires:
    context_has: [html_content, vendor, os_type, protocol]
  priority: 10  # higher = checked first when multiple skills match
---
```

```yaml
---
name: version-detection
owner_agent: doc-monitor
triggers:
  task_types: [detect_version, check_new_releases, full_monitor_cycle]
  requires:
    context_has: [vendor, os_type]
    context_lacks: [html_content]  # if no HTML, this is a version-only check
  priority: 5
---
```

**Key design choice:** `full_monitor_cycle` appears in BOTH skills' trigger lists. When the Orchestrator sends Step 1 (full monitor cycle), both skills activate — `vendor-doc-extraction` runs first (higher priority), then `version-detection`. This is the correct behavior: a full cycle does both extraction and version checking.

#### TaskContext: What the Agent Knows at Dispatch Time

When the Orchestrator dispatches a task to an agent, it provides a `TaskContext` — a structured object describing what needs to happen. This context is what skill routing evaluates against.

```python
@dataclass
class TaskContext:
    """
    Passed from Orchestrator to Agent at dispatch time.
    Contains everything the agent needs to route to the right skill.
    """
    # What kind of task is this?
    task_type: str  # e.g., "extract_attributes", "full_monitor_cycle", "generate_code"

    # What entity is this about?
    vendor: Optional[str] = None       # "cisco", "arista"
    os_type: Optional[str] = None      # "ios", "iosxe", "eos"
    protocol: Optional[str] = None     # "bgp", "ospf", "vrf"

    # What data is available?
    html_content: Optional[str] = None         # for doc extraction
    parser_class: Optional[str] = None         # for parser analysis
    gap: Optional[GapAnalysis] = None          # for code generation
    attribute_catalog: Optional[dict] = None   # for gap analysis

    # Metadata
    cycle_id: str = ""
    step_number: int = 0

    def has(self, field: str) -> bool:
        """Check if a field is present and non-None."""
        return getattr(self, field, None) is not None

    def context_fields(self) -> set[str]:
        """Return names of all non-None fields."""
        return {f for f in self.__dataclass_fields__ if self.has(f)}
```

#### SkillRouter: The Selection Logic

```python
class SkillRouter:
    """
    Selects which skill(s) to activate for a given TaskContext.
    Each agent has one SkillRouter instance.

    Routing is declarative — no LLM calls, no fuzzy matching.
    Skills declare their trigger conditions in YAML frontmatter.
    The router evaluates conditions against the TaskContext.
    """

    def __init__(self, agent_name: str, skill_loader: SkillLoader):
        self.agent_name = agent_name
        self.skill_loader = skill_loader
        # L1: load metadata for all skills owned by this agent
        self._skills = [
            s for s in skill_loader.list_skills()
            if s.owner_agent == agent_name
        ]

    def select_skills(self, context: TaskContext) -> list[SkillMetadata]:
        """
        Return matching skills sorted by priority (highest first).

        A skill matches if:
        1. task_type is in the skill's trigger.task_types list
        2. All fields in trigger.requires.context_has are present in context
        3. No fields in trigger.requires.context_lacks are present in context

        Returns empty list if no skills match (agent falls back to
        hardcoded behavior — graceful degradation).
        """
        matched = []
        for skill in self._skills:
            triggers = skill.triggers

            # Condition 1: task type must match
            if context.task_type not in triggers.task_types:
                continue

            # Condition 2: required context fields must be present
            if triggers.requires_has:
                if not all(context.has(f) for f in triggers.requires_has):
                    continue

            # Condition 3: excluded fields must be absent
            if triggers.requires_lacks:
                if any(context.has(f) for f in triggers.requires_lacks):
                    continue

            matched.append(skill)

        # Sort by priority (descending) — higher priority skills run first
        matched.sort(key=lambda s: s.triggers.priority, reverse=True)
        return matched

    def select_one(self, context: TaskContext) -> Optional[SkillMetadata]:
        """Convenience: return highest-priority match, or None."""
        matches = self.select_skills(context)
        return matches[0] if matches else None
```

#### SkillLoader: Reading Skill Content

Once routing selects a skill, the `SkillLoader` handles the three-level loading:

```python
class SkillLoader:
    """
    Loads skill files at task time with progressive disclosure.
    L1 (metadata) is cached at init.
    L2 (SKILL.md body) loads when a skill is selected by the router.
    L3 (references) loads on-demand based on task context.
    """

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._metadata_cache: dict[str, SkillMetadata] = {}
        self._load_all_metadata()  # L1: warm cache at init

    def _load_all_metadata(self):
        """Scan skills_dir, parse YAML frontmatter from each SKILL.md."""
        for skill_dir in self.skills_dir.iterdir():
            if (skill_dir / "SKILL.md").exists():
                meta = self._parse_frontmatter(skill_dir / "SKILL.md")
                self._metadata_cache[meta.name] = meta

    def list_skills(self) -> list[SkillMetadata]:
        """L1: Return cached metadata for all available skills."""
        return list(self._metadata_cache.values())

    def load_skill(self, skill_name: str) -> SkillBody:
        """L2: Load and return the full SKILL.md body (excluding frontmatter)."""
        ...

    def load_reference(self, skill_name: str, ref_name: str) -> str:
        """L3: Load a specific named reference file."""
        ...

    def load_vendor_reference(self, skill_name: str, vendor: str, os_type: str) -> str:
        """
        L3: Load vendor-specific reference by naming convention.
        Looks for: references/{vendor}-{os_type}-*.md
        Example: references/arista-eos-selectors.md
        """
        ...

    def list_references(self, skill_name: str) -> list[str]:
        """List available reference files for a skill (for discovery)."""
        ...
```

#### How It All Fits Together: End-to-End Flow

```
Orchestrator dispatches Step 1 (full_monitor_cycle) to Doc Monitor Agent
    |
    v
Doc Monitor creates TaskContext:
    task_type = "full_monitor_cycle"
    vendor = "arista"
    os_type = "eos"
    protocol = "bgp"
    html_content = "<html>..."
    |
    v
SkillRouter.select_skills(context) evaluates:
    vendor-doc-extraction:  task_type ✓  context_has[html_content,vendor,os_type,protocol] ✓  → MATCH (priority 10)
    version-detection:      task_type ✓  context_lacks[html_content] ✗ (html_content IS present) → NO MATCH
    |
    v
Result: [vendor-doc-extraction] activated
    |
    v
SkillLoader.load_skill("vendor-doc-extraction")  → L2: reads SKILL.md body
    |
    v
Agent reads SKILL.md instructions:
    "Step 3: Load the appropriate vendor selectors reference file"
    |
    v
SkillLoader.load_vendor_reference("vendor-doc-extraction", "arista", "eos")
    → L3: reads references/arista-eos-selectors.md
    |
    v
Agent executes extraction using loaded selectors
    |
    v
Later in the same step, agent needs version detection:
    Updates context: task_type = "detect_version", html_content = None
    |
    v
SkillRouter.select_skills(updated_context):
    version-detection:      task_type ✓  context_has[vendor,os_type] ✓  context_lacks[html_content] ✓ → MATCH
    |
    v
SkillLoader.load_skill("version-detection") → L2 + L3 as needed
```

#### Edge Cases and Fallbacks

| Scenario | Behavior |
|----------|----------|
| No skills match the TaskContext | Agent falls back to hardcoded behavior (graceful degradation). Logged as a warning. This is important for Phase 0-1 when not all skills exist yet. |
| Multiple skills match with same priority | All are activated in declaration order. Agent runs each sequentially. |
| Skill file is missing or corrupt | SkillLoader raises `SkillLoadError`. Agent falls back to hardcoded behavior. Alert sent to Slack. |
| New task type not in any skill's trigger list | Same as "no match" — falls back to hardcoded, logged as warning. This is how new capabilities get added before skills are written for them. |
| Agent's skill directory is empty | Agent operates entirely on hardcoded logic (pre-skills behavior). No errors. |

#### Why Declarative Routing, Not LLM-Based

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| **Declarative (chosen)** | Zero latency, zero cost, deterministic, testable, no false triggers | Requires manual trigger definition in frontmatter | **Best fit** — agents have 1-3 skills, task types are well-defined |
| **LLM-based** (read all skill descriptions, ask model to pick) | Handles ambiguity, works for 100+ skills | Adds LLM call latency + cost on every task, non-deterministic | Overkill — we have <20 skills total |
| **Keyword matching** (match task description against skill description) | Simple, no LLM needed | Fragile, false positives, hard to debug | Too unreliable for production |
| **Hardcoded mapping** (dict of agent → skill) | Simplest | Can't handle conditional routing (same agent, different skills based on context) | Doesn't solve the problem |

Declarative routing is the right choice for a system with a small, well-defined skill set where task types are known in advance. If the system grows beyond ~50 skills, LLM-based routing with L1 metadata becomes worth reconsidering (see ADR-004 below).

---

## Data Models — Additions

These models supplement the existing v3 data models. No existing models are changed.

### Skill Routing Layer

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `TaskContext` | Describes a dispatched task for skill routing | `task_type`, `vendor`, `os_type`, `protocol`, `cycle_id`, `step_number`, plus task-specific optional fields (`html_content`, `parser_class`, `gap`, `attribute_catalog`) |
| `SkillTrigger` | Declares when a skill should activate | `task_types: list[str]`, `requires_has: list[str]`, `requires_lacks: list[str]`, `priority: int` |

### Skill Layer

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `SkillMetadata` | L1 metadata parsed from YAML frontmatter | `name`, `description`, `version`, `owner_agent`, `triggers: SkillTrigger`, `last_updated` |
| `SkillEvalResult` | Result of running a skill's eval suite | `skill_name`, `eval_id`, `passed`, `assertions_total`, `assertions_passed`, `failures: list[str]`, `run_timestamp` |
| `SkillUpdateProposal` | Proposed change to a skill file | `skill_name`, `target_file`, `change_type` (add/modify/delete), `old_content_hash`, `new_content`, `evidence` (feedback IDs that motivated this change), `eval_before`, `eval_after` |
| `SkillHealthReport` | Aggregated health metrics | `skill_name`, `period`, `eval_pass_rate`, `feedback_count`, `negative_feedback_count`, `improvement_opportunities` |
| `SkillRouteLog` | Audit trail for skill selection decisions | `cycle_id`, `step_number`, `agent_name`, `task_context_summary`, `skills_evaluated: int`, `skills_matched: list[str]`, `skill_selected: str`, `fallback_used: bool` |

### Feedback Routing

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `FeedbackRoute` | Mapping from feedback to skill target | `feedback_type`, `condition`, `target_skill`, `target_file` |

### Updated Existing Models

| Model | Addition | Purpose |
|-------|---------|---------|
| `LLMCallRecord` | `skill_name: Optional[str]`, `skill_reference_tokens: int` | Track LLM usage per skill and token overhead from reference files |
| `ValidationCycleResult` | `skill_updates_proposed: int`, `skill_evals_run: int`, `skill_fallbacks: int` | Track skill activity per cycle, including how often agents fell back to hardcoded behavior |

---

## Risk Analysis — Skills-Specific

| Risk | Level | Probability | Mitigation |
|------|-------|-------------|------------|
| **Skill drift:** agent writes bad instructions that compound | MEDIUM | 25% | All skill changes go through PR review (same as code). Eval regression checks prevent quality decline. `history/` directory enables instant rollback. |
| **Context bloat:** too many reference files inflate LLM costs | LOW | 15% | Progressive loading (L1/L2/L3) ensures only relevant references load. Monitor token usage per skill via `LLMCallRecord.skill_reference_tokens`. |
| **Skill conflicts:** two skills give contradictory instructions | LOW | 10% | Each agent owns its skill(s). No cross-agent skill sharing initially. Skill Evolution Agent can detect conflicts in Phase 4. |
| **Over-automation:** agent rewrites skill incorrectly, auto-merges | LOW | 5% | Skill PRs require human approval (same policy as code PRs). Auto-merge is always disabled per v3 design. |
| **Eval gaming:** agent optimizes for eval metrics but degrades real quality | MEDIUM | 20% | Evals are curated by humans initially. New evals added from real failures. Eval set diversity reviewed quarterly. Skill Evolution Agent cannot modify eval assertions (human-only). |
| **Skill maintenance burden exceeds benefit** | LOW | 10% | Earn-the-complexity: start with one skill (Phase 0). If `.md` reference files don't work as well as Python code, stop. Each phase is a go/no-go gate. |

---

## Updated Success Metrics

These supplement the existing v3 metrics. Existing targets are unchanged.

### Skill Layer Metrics

| Metric | Target | Measurement | Starting Phase |
|--------|--------|-------------|---------------|
| Skill eval pass rate | >90% per skill | EvalRunner results | Phase 1 |
| Skill self-update frequency | Track (increasing = learning) | Skill-update PR count | Phase 2 |
| Skill update approval rate | >80% | Merged / proposed skill-update PRs | Phase 2 |
| Time-to-fix for scraper failures | <4 hours (auto) | Detection to skill-fix PR | Phase 1 |
| False positive rate decline | Quarter-over-quarter improvement | FP rate tracked with/without catalog | Phase 2 |
| Prompt template evolution impact | Measurable increase in first-attempt success | Before/after prompt change success rates | Phase 3 |
| Skill context token overhead | <15% of total prompt tokens | `LLMCallRecord.skill_reference_tokens` / total | Phase 1 |
| Maintenance effort attribution | >50% of skill changes proposed by agents (vs. manual) | Agent-proposed vs human-authored skill PRs | Phase 4 |

### Go/No-Go Gates for Skills

| Gate | Phase | Criteria | Action if Fail |
|------|-------|----------|---------------|
| Skill file usability | Phase 0 | Arista scraper selectors work as `.md` files with same extraction accuracy | Abandon skills approach, keep rules in Python |
| Eval loop viability | Phase 1 | EvalRunner reliably detects regressions in vendor-doc-extraction skill | Simplify: keep skill files but drop self-improvement loop |
| Feedback routing value | Phase 2 | False-positive-catalog reduces FP rate by >=2 percentage points | Keep skills as static references, drop auto-update |
| Prompt evolution ROI | Phase 3 | Agent-proposed prompt changes improve first-attempt success by >=5% | Keep manual prompt tuning, drop agent-proposed updates |
| Skill Evolution Agent ROI | Phase 4 | Agent-proposed skill updates have >80% approval rate | Drop Skill Evolution Agent, keep manual skill maintenance |

---

## Decision Record

### ADR-001: Skills as Markdown Files, Not Code

**Context:** Should skill instructions and reference data live in Python code, YAML, JSON, or Markdown?

**Decision:** Markdown (`.md`) files.

**Rationale:**
- LLMs read and write Markdown natively — no parsing overhead
- Human-readable and reviewable in GitHub PRs
- Supports structured data (tables, code blocks) and prose instructions
- Git-versioned with full diff/blame/rollback
- YAML frontmatter provides machine-readable metadata without sacrificing readability
- Agents can rewrite Markdown more reliably than Python code (lower risk of syntax errors)

**Rejected alternatives:**
- Python code: agents can generate it, but rewriting instructions-as-code risks subtle bugs
- YAML/JSON: good for structured data, poor for prose instructions and examples
- Database records: lose Git versioning, harder to review, not diffable

### ADR-002: One Skill Per Agent (Initially)

**Context:** Should skills be shared across agents or scoped to a single agent?

**Decision:** Each agent owns its skill(s). No cross-agent sharing in Phases 1-3.

**Rationale:**
- Avoids conflicts when two agents interpret the same skill differently
- Clear ownership makes feedback routing unambiguous
- Simpler mental model for engineers reviewing skill-change PRs
- Cross-cutting skills (like `code-style-conventions`) are read-only for non-owning agents

**Future:** Phase 4 may introduce shared reference skills if clear use cases emerge.

### ADR-003: Human-Only Eval Assertion Modification

**Context:** Can the Skill Evolution Agent modify eval assertions?

**Decision:** No. Only humans can add, modify, or remove eval assertions.

**Rationale:**
- Eval assertions are the ground truth that skills are measured against
- If agents can modify their own eval criteria, they can "game" the metrics
- This is the single most important safeguard against skill drift
- Agents CAN propose new eval cases (with assertions), but a human must approve them in the PR

### ADR-004: Declarative Skill Routing, Not LLM-Based

**Context:** When an agent owns multiple skills, how does it select the right one for a given task?

**Decision:** Declarative trigger conditions in SKILL.md YAML frontmatter, evaluated by a `SkillRouter` against a `TaskContext` dataclass. No LLM calls for routing.

**Rationale:**
- Zero latency and zero cost per routing decision (pure Python pattern matching)
- Deterministic: same TaskContext always selects the same skill(s), making debugging straightforward
- Testable: routing logic can be unit-tested with mock TaskContexts
- Sufficient: we have <20 skills total across 6 agents. The combinatorics don't justify an LLM call.
- Graceful degradation: if no skill matches, the agent falls back to hardcoded behavior. This is critical during the phased rollout when not all skills exist yet.

**Rejected alternatives:**
- LLM-based routing (read all skill descriptions, ask model to pick): adds latency + cost on every task, non-deterministic, overkill for <20 skills
- Keyword matching against task descriptions: fragile, false positives, hard to debug
- Hardcoded agent→skill mapping: can't handle conditional routing (same agent, different skills based on context)

**Revisit trigger:** If the system grows beyond ~50 skills per agent or task types become unpredictable, reconsider LLM-based routing with L1 metadata as the selection prompt.

---

## Next Steps

1. **Review this addendum** — Engineering team reviews proposed skill design
2. **Phase 0 experiment** — When building the Arista EOS BGP scraper, extract CSS selectors into `arista-eos-selectors.md` instead of hardcoding. Measure: does extraction accuracy change?
3. **TaskContext + SkillRouter prototype** — Build the `TaskContext` dataclass, `SkillRouter`, and `SkillLoader` as part of Phase 1 infrastructure. Write unit tests for routing logic using mock TaskContexts.
4. **Define task_types enum** — Enumerate all task types across agents (extract_attributes, detect_version, analyze_parser, compare_gaps, generate_code, validate_code, full_monitor_cycle, etc.) as the canonical vocabulary for trigger conditions.
5. **First eval suite** — Write 5-10 eval cases for `vendor-doc-extraction` using known Arista EOS pages
6. **Go/No-Go** — Based on Phase 0 results, decide whether to proceed with full skill rollout

---

**Recommendation:** The skills layer is a natural extension of the v3 architecture, not a replacement. Start with the Phase 0 experiment (extract selectors into `.md`). If it works — and it should, because it's just moving data from Python to files — proceed incrementally through each phase. If it doesn't, we've lost 2 days and learned something.
