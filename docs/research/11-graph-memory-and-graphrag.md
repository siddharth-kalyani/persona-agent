# 11 — Relationship Graph, Graph Memory and GraphRAG: where a graph earns its place

**Track:** Should PersonaAgent add a graph (and specifically GraphRAG) for relationships, commitments and memory, or do Postgres tables suffice?
**Date:** 2026-10-09 · **Status:** v1.0 research report (completed 2026-10-11) · **Audience:** founders and engineers making the "graph or columns" call

> **Founder decision F8 (2026-10-11):** the MVP keeps option A (plain relationship tables). Option D is adopted at **company level** for later phases (shared context, opt-in team spaces, company graph) — see `../02-solution-architecture.md` §8.6. Open questions are parked in `../05-decisions-and-open-questions.md` §7 (research backlog).

**Founder question:** "Add a graph for relationships, preferably GraphRAG, and justify it. If a normal DB with columns can do it, leave it."

**Builds on (does not repeat):** `04-aws-data-multitenancy-security.md` §2.4 (graph DB options, Neptune prices, Hyderabad gap) and `05-persona-modeling-and-memory.md` §4 (Mem0/Zep/Graphiti, LoCoMo/LongMemEval) and §7.11 (v2 graph gate: "≥ 15% failure on multi-hop or 'what changed' questions that SQL + RAG can't fix"). Redaction and token semantics come from `10-security-threats-and-redaction.md` §6.7.

**Confidence legend:** **[High]** = primary source fetched this session and the claim transfers directly. **[Med]** = primary source verified but transfer to our setting needs inference, or a reputable secondary source. **[Low]** = estimate or expert judgement, labelled as such. **Unverified** = could not confirm this session; listed in §12.

---

## 0. Executive summary

**Recommendation in one paragraph.** Do **not** add a graph database or Microsoft-style GraphRAG to the MVP. **Do** add a *small graph inside Postgres*: two tables (`graph_node`, `graph_edge`) filled **only from metadata we already parse** (senders, recipients, chat members, meeting attendees, Entra manager, client domains, commitments). In **v1.5**, when meeting memory, recall Q&A and pre-meeting briefs ship, add a **"GraphRAG-lite" retrieval step**: expand one hop from the people and clients named in a question, pull the linked evidence, and merge it with vector search. Ship that step **only if it passes the evaluation gate in §8**. Everything else the founder listed is ordinary columns and joins. This is option **B now, C in v1.5, D later or never** in §3. It refines, and does not contradict, the existing "graph-in-tables in Postgres; Neptune later" decision (R04 §2.4, R05 §7.11).

**Why (evidence):**
- **Our data is already a graph, and a more accurate one than GraphRAG would extract.** Exchange, Teams and calendar metadata give exact edges: who sent what to whom, when, in which thread or meeting. The redaction vault's tokens (`⟦PERSON_k3d9⟧`, `⟦CLIENT_9f2⟧`) are already canonical, per-tenant entity IDs, clustered from directory data and headers (R10 §6.7). GraphRAG's expensive step is LLM entity and relationship extraction. Microsoft estimates it at "roughly **75%** of indexing cost". That step exists to recover structure we get for free. [High on Microsoft's docs; Med on the transfer to us]
- **Where graph RAG helps:**
  - **Global "sensemaking" summaries** over corpora of about 1M tokens. LLM judges preferred GraphRAG over vector RAG **72–83%** of the time on comprehensiveness and **62–82%** on diversity (Edge et al., v2 Feb 2025).
  - **Multi-hop questions**, by **+1.6 to +10 points** depending on method and corpus. HippoRAG 2 was the most consistent (Han et al., v3 Mar 2026; GraphRAG-Bench, ICLR 2026). [High]
- **Where graph RAG hurts:**
  - **Single-hop, detail questions.** Vanilla RAG with reranking beat MS-GraphRAG on fact retrieval by **11.6 points** on one corpus and **26 points** on another.
  - **Cost.** Indexing the same corpus took GraphRAG **115.5M input tokens and 277 min**. HippoRAG 2 took 9.2M tokens; dense indexing took 12 min.
  - **Inflated evaluations.** After LLM-judge biases were removed, LightRAG's win rate over naive RAG fell from **66.7% to 39.1%** (Zeng et al., v2 Aug 2026). [High]
- **Temporal-graph agent memory is not a clear win either:**
  - Zep's **+18.5%** on LongMemEval is measured against *full context*, not tuned RAG.
  - A 2026 controlled study finds that "many performance differences are driven by foundational system settings". Its graph extraction took **7.6× longer** (1,181 vs 156 min).
  - A second 2026 unified benchmark could not finish Zep's LongMemEval indexing within two days.
  - Graphs *do* help temporal questions. [High]
- **The managed AWS options don't fit our constraints:**
  - **Bedrock Knowledge Bases GraphRAG** accepts only S3 data sources. It allows no graph-build customisation and 1,000 files per data source by default. It is **not offered in Mumbai or Hyderabad**.
  - **Neptune Analytics** costs at least **$350/month per graph** in the US and **$403 in Mumbai**. It is **absent from Hyderabad** and allows **one vector index per graph**.
  - **AgentCore Memory** has no graph strategy.
  - **Apache AGE** is not on Aurora or RDS. **SQL/PGQ was reverted from PostgreSQL 19** in Beta 4 (24 Sep 2026). [High]
- **Postgres is fast enough by a wide margin.** Measured locally on PostgreSQL 16 with row-level security on and 10 users × 281k edges in one table:

  | Query | p50 | p95 |
  |---|---|---|
  | 1-hop neighbours | 0.3 ms | — |
  | 2-hop expansion | 1.1 ms | — |
  | Pre-meeting brief context | 1.7 ms | — |
  | Brief context, most-connected attendees | 5.3 ms | — |
  | Capped "GraphRAG-lite" expansion | 3.6 ms | 7.6 ms |
  | Full client-exclusion closure | 37 ms | — |
  | Full client-exclusion closure, biggest client | 55 ms | — |

  [Med: laptop, not Aurora; §5.5]
- **Costs** (per user-month unless stated):
  - **Graph-in-Postgres:** about **$0.01–0.02**.
  - **Per-tenant Neptune Analytics:** about **$3.50** at 100-seat tenants. That is roughly **8×** the whole per-user infrastructure budget in R04 (about $0.44).
  - **Full GraphRAG indexing** of a 150k-message mailbox: an estimated **$170–$750+ per user, one-off**, on Haiku 4.5 batch. That equals **4–18 months** of a $40 seat. [Low on usage; High on unit prices; §7]
- **Where a graph *database* may eventually pay:** a tenant-wide **"who knows whom / warm path / relationship strength"** Enterprise add-on.
  - The market charges premium prices: Affinity **$2,000–2,700/user/year**; Salesforce Einstein Relationship Insights **$50–150/user/month**; Dynamics 365 offers enhanced who-knows-whom only with specific Sales licences.
  - Even then, start in SQL. Move to Neptune Analytics per enterprise tenant only on the triggers in §9. [High on prices; Low on our demand]

**What the founder gets, by option (detail in §3):**

| Option | Complexity for a learner | Effort | Value | Verdict |
|---|---|---|---|---|
| **A.** No graph: relationship columns + SQL joins | 1/5 | 0 extra (already planned) | Covers the MVP | Fallback if the MVP is squeezed |
| **B.** Simple graph in Postgres (nodes + edges from metadata) | 2/5 | +1–2 eng-weeks | One pattern for scoping, briefs, ledger links; base for C | **Recommended for the MVP** |
| **C.** B + GraphRAG-lite retrieval (1-hop expansion + vector merge) | 3/5 | +1.5–3 eng-weeks | Likely modest lift on multi-hop questions | **v1.5, only if the §8 gate passes** |
| **D.** Full GraphRAG / Neptune / Bedrock KB GraphRAG | 5/5 | 8–16+ eng-weeks plus operations | Low for us now | **Later / optional** (Enterprise add-on research) |

---

## 1. What "graph" and "GraphRAG" mean here

The word covers four different things. Only the first two belong in the MVP.

1. **A graph data model.** People, clients, threads, meetings, atoms and commitments as nodes, linked by typed edges. It can live in ordinary Postgres tables. *This is cheap.*
2. **Graph-shaped queries.** "1–3 hops from X", written as SQL joins, `LATERAL` subqueries or recursive CTEs. *Postgres does this well at our sizes (§5.5).*
3. **Graph-expanded retrieval** ("local" GraphRAG, called *GraphRAG-lite* here). Seed entities → neighbours → linked evidence → merge with vector hits → rerank. Bedrock KB "GraphRAG" is a managed version of this: vector search first, then traversal to related chunks and entities. No community summaries are documented for it.
4. **Microsoft-style GraphRAG.** An LLM extracts a knowledge graph from all text. Community detection (Leiden) groups entities, an LLM writes "community reports", and global questions are answered by map-reduce over those reports. *This is expensive. It pays off mainly for corpus-wide summary questions.*

A **graph database** (Neptune, Neo4j) is a fifth, separate decision. It is a storage choice and is needed only when the queries in (2) outgrow SQL.

---

## 2. Evidence review

### 2.1 Graph RAG: what improved, where it hurt, what it cost

| Study (date) | Setting | Where the graph helped | Where it hurt or added nothing | Cost / latency | Conf. |
|---|---|---|---|---|---|
| **Edge et al., MS GraphRAG** (arXiv 2404.16130; v1 Apr 2024, v2 19 Feb 2025) | Podcast (~1M tokens) and News (~1.7M tokens); 125 global questions per dataset; gpt-4-turbo; LLM-judged head-to-head | Comprehensiveness win rate vs vector RAG **72–83%** (Podcast) and **72–80%** (News); diversity **75–82%** / **62–71%**. Claim-based re-check agreed. | Vector RAG gave "the most direct responses across all comparisons"; empowerment was mixed. Global questions only. | Root summaries need **9–43× fewer tokens** than summarising source text (26,657–39,770 tokens per query). Indexing Podcast took **281 min**. Graph sizes: 8,564 nodes / 20,691 edges; 15,754 / 19,520 | High |
| **LazyGraphRAG** (Microsoft Research blog, 25 Nov 2024; Jun 2025 note) | 5,590 AP articles; 100 synthetic queries (50 local, 50 global); LLM-judged | Matches GraphRAG global answer quality at **>700× lower query cost**. At 4% of that cost it beats all methods on local and global queries. | Lowest budget does not beat GraphRAG global search on global queries | Indexing cost equals vector RAG, **0.1%** of full GraphRAG. Shipped in Microsoft Discovery / Azure Local; open-source availability unverified | Med (vendor blog) |
| **FastGraphRAG** (Microsoft GraphRAG docs) | Option inside GraphRAG | Summary questions at "much lower language model cost" | Graph is "quite a bit noisier" (noun phrases from spaCy/NLTK, co-occurrence edges) | Extraction is "roughly 75%" of standard indexing cost | High (docs) |
| **LightRAG** (Guo et al., v3 Apr 2025) | UltraDomain (0.6–5.1M tokens); 125 questions per dataset; GPT-4o-mini judge | Self-reported overall win rate vs NaiveRAG **60–85%**; about **50–55%** vs GraphRAG | Independent re-tests: avg F1 **6.6** vs 57.0 for dense retrieval (HippoRAG 2 paper); below NaiveRAG after debiasing (Zeng et al.) | Retrieval under 100 tokens and one call, vs GraphRAG's ~610k tokens over 610 communities | Med |
| **HippoRAG 2** (Gutiérrez et al., ICML 2025) | 7 QA sets; Llama-3.3-70B; NV-Embed-v2 | Avg F1 **59.8** vs **57.0** for dense retrieval; the only structured method that did not lose on simple QA | GraphRAG **49.6**, RAPTOR **48.8**, LightRAG **6.6**: all *below* plain dense retrieval | Indexing 11,656 passages: dense **12 min**; HippoRAG 2 **99.5 min, 9.2M in / 3.0M out tokens**; LightRAG 235 min, 68.5M / 18.3M; GraphRAG **277 min, 115.5M / 36.1M** | High |
| **Han et al., "RAG vs. GraphRAG"** (arXiv 2502.11371; v3 4 Mar 2026) | NQ, HotpotQA, MultiHop-RAG, QFS sets; Llama-3.1-8B/70B; GPT-4o-mini graph builder | Multi-hop: HippoRAG 2 **+2.97 F1** (HotpotQA) and **+3.25** (MultiHop-RAG) over RAG; community-local **+1.6 / +2.0**. Running both and concatenating ("Integration") gave **+6.4%** on MultiHop-RAG (70B). | Single-hop NQ: RAG **64.78** beat all graph methods. Global community search was *below* RAG on QA. KGs held only **~65.5–65.8%** of answer entities. Pairwise summary judgments flip when answer order is swapped. | Construction **5,560–7,702 s** vs 135 s for RAG | High |
| **GraphRAG-Bench, "When to use Graphs in RAG"** (Xiang et al., **ICLR 2026**; v3 22 Feb 2026) | Novel and Medical corpora; 4 task levels; GPT-4o-mini | Novel corpus: complex reasoning **53.38** (HippoRAG 2) and **50.93** (MS-GraphRAG) vs **42.93** for RAG + rerank; summarisation **64.40** (MS-GraphRAG) vs **51.30** | Fact retrieval: RAG + rerank **60.92** vs MS-GraphRAG **49.29**. Medical corpus: MS-GraphRAG below RAG on *every* task (fact 38.63 vs 64.73) | Tokens per query: vanilla ~900; HippoRAG 2 ~1,000; MS-GraphRAG local ~39k; global **~331k** (table) or ~40k (prose). The paper is inconsistent here. | High (numbers); Med (token table) |
| **Zeng et al., "How Significant Are the Real Performance Gains?"** (arXiv 2506.06331; v2 13 Aug 2026) | MS GraphRAG, LightRAG, FastGraphRAG vs NaiveRAG; debiased judging | FastGraphRAG still +21% relative over LightRAG; MS GraphRAG +11% | LightRAG vs NaiveRAG **66.70% → 39.06%**; vs MS GraphRAG **56.38% → 32.33%**. Swapping answer order moved win rates by **>30%**. A 25-token length gap moved them by **>50%**. LightRAG scored 90/10 *against itself* under the old protocol. | — | High |
| **WildGraphBench** (Wang et al., 2–3 Feb 2026) | 1,100 questions over Wikipedia-cited sources | Helps "multi-fact aggregation when evidence comes from a moderate number of sources" | Weaker on summaries: high-level statements crowd out fine detail | — | Med (abstract only) |

### 2.2 Temporal knowledge graphs for agent memory

| Study (date) | Result | Caveat | Conf. |
|---|---|---|---|
| **Zep / Graphiti** (Rasmussen et al., Jan 2025) | DMR **94.8** vs full conversation 94.4 vs MemGPT 93.4 (gpt-4-turbo). LongMemEval_s (gpt-4o): **71.2 vs 60.2** for full context (+18.5%), using **1.6k vs 115k** context tokens; latency **2.58 vs 28.9 s**. Temporal **62.4 vs 45.1**. | The baseline is full context, not tuned RAG. Single-session-assistant fell **94.6 → 80.4**. The paper calls DMR too small and single-hop. | High |
| **Mem0 / Mem0g** (Chhikara et al., Apr 2025) | LoCoMo J: Mem0g **68.44** vs Mem0 66.88. The graph helps temporal (58.13 vs 55.51) and open-domain questions. | The graph **hurts multi-hop** (47.19 vs 51.15). p95 latency 2.59 vs 1.44 s; memory 14k vs 7k tokens. Zep disputes the Mem0-run comparison (R05 §4.3). | High |
| **"Does Memory Need Graphs?"** (Hu et al., v1 3 Jan, v3 10 Feb 2026) | The graph raised LongMemEval retrieval recall (R@5 0.928 → 0.969, GPT-4o-mini) and session-value QA | Key-value QA was **worse with the graph in all four settings**. "Many performance differences are driven by foundational system settings." Graph extraction **1,181 vs 156 min** (LME-S). | High (ACL 2026 acceptance unverified) |
| **"Memory in the LLM Era"** (Wu et al., v1 Apr, v3 6 Aug 2026) | Zep was the best graph method on LoCoMo (LLM-judge 77.8 / 80.8). "Graph performs better on temporal reasoning questions." | Mem0g trailed plain Mem0 on LoCoMo. **Zep's LongMemEval indexing did not finish within two days.** Query latency: Zep 537 ms, Mem0g 3,783 ms. Lessons: "retaining raw dialogue context is essential"; triple-only extraction loses information. | High |

### 2.3 What this means for PersonaAgent

1. **Graph structure helps two question types: multi-hop/relational questions and corpus-wide summaries.** It *hurts* single-hop, detail-oriented questions when applied blindly. So graph expansion must be **routed** (Han et al.'s "Selection") or **merged** ("Integration"), never forced on every query. [High]
2. **The expensive half of GraphRAG is optional for us.** Most published methods spend their tokens recovering entities and relations from prose. Our people, clients, threads and meetings arrive as structured metadata. Commitments, requirements and decisions are already extracted once by the memory-atom pipeline (R05 §5.3), and those atoms *are* our typed facts. [Med]
3. **Expect small, fragile gains, and measure them ourselves.** Published wins shrink sharply once judge position and length biases are controlled. Our §8 gate uses debiased judging and gold evidence IDs. [High]
4. **Keep raw L1 evidence as the answer source.** The graph only *routes* to evidence. This agrees with R05 §4.5 and with the 2026 finding that keeping raw dialogue matters more than graph structure. [High]
5. **Time matters more than "graphness".** The one consistent graph win in agent memory is temporal reasoning. We get most of it from **validity ranges on edges and atoms** plus **date resolution in code** (R05 §5.4), with no graph engine. [Med]

---

## 3. Simplest viable options (for a learning founder and a 5–6-engineer MVP)

The options are rated on **complexity for a learner** (1 = ordinary SQL, 5 = a new distributed subsystem), **effort** in engineer-weeks on top of the current plan, and **value**. Effort figures are estimates [Low], scaled against R05's 3–4 engineer-weeks for the v1 memory layer.

### Option A — No graph: relationship columns + SQL joins

- **What you build:**
  - `persons` (token, org token, Entra manager token)
  - `orgs` (client accounts, verified domains)
  - `relationships` (user × contact, as in R05 §7.12)
  - participant link tables (message recipients, chat members, meeting attendees)
  - `commitments` (owner, counterparty, client, due date, status, evidence)
  - `memory_atoms` (subject, speaker and assignee tokens)
  - **scope tags** (`allowed_orgs`) on every content row and vector

  Queries are plain joins, plus one recursive CTE for the manager chain.
- **New services or skills:** none beyond SQL. **Ops burden:** none new.
- **Failure modes:**
  - Every new "relationship question" needs another hand-written join across several tables.
  - A new table that forgets its scope tags silently breaks client exclusion.
  - Generic expansion (option C) is awkward to add later.
- **Effort:** 0 extra; it is already in the MVP plan. **Value:** covers what the MVP sells (relationship-aware drafts, ledger v0, client scoping).
- **Use cases covered:** 1, 2, 3, 4, 5; simple versions of 6 (briefs).

### Option B — A simple graph inside Postgres (two tables, metadata only) — **recommended for the MVP**

- **What you build:**
  - `graph_node` and `graph_edge` (§5.2), with the same row-level security as every other table.
  - The ingestion worker writes edges **in the same transaction** as the message, chat, meeting, atom or commitment row. Edges come only from metadata and existing extractor outputs; **no new LLM calls**.
  - About six query functions: `people_at(client)`, `recent_items_with(person, window)`, `closure(client)`, `brief_context(attendees)`, `neighbours(node, types, cap)`, `manager_chain(person)`.
  - A nightly job that refreshes node degree, used for hub suppression.
- **New skills:** thinking in nodes and edges; `LATERAL` joins; recursive CTEs (only for org charts). **No new service.**
- **Ops burden:** none new. About **52 MB per heavy user**, measured with two covering indexes.
- **Failure modes:**
  - **Hub fan-out.** The user's own node, all-hands meetings and big distribution lists connect to everything, so cap and skip them.
  - **Duplicate entities** if the vault fails to merge aliases.
  - **Orphaned edges** after an exclusion purge, if purge code skips the edge table.
  - **Over-modelling:** edge types nobody queries.
- **Effort:** +1–2 engineer-weeks over A. **Value:**
  - One closure query for client exclusion (measured 37–55 ms p50).
  - Brief context in about 2–5 ms.
  - Ledger links (owner → counterparty → client) without extra tables.
  - The substrate for C, and a ready-made export format if a graph database is ever needed: a nodes/edges CSV is Neptune's bulk-load format.
- **Deferral is free.** Every edge is derived deterministically from rows that A stores anyway. If the 12 weeks get tight, ship A and backfill B with `INSERT … SELECT` at v1.5, with no re-reading of mailboxes.
- **Use cases covered:** 1–6 (briefs and structured recall), one pattern for 3 and 4.

### Option C — B + a "GraphRAG-lite" retrieval step — **v1.5, behind the §8 gate**

- **What you build:**
  - **Seed detection.** Named people and clients are *already* tokens in the L1-redacted question, so no NER is needed. Calendar-event resolution reuses the R05 §5.4 parser.
  - **A capped 1-hop expansion** (measured 3.6 ms p50 / 7.6 ms p95), with 2-hop only along typed paths such as client → people → items.
  - Map expanded items to their chunk and atom IDs.
  - **Merge** with vector and full-text hits by reciprocal-rank fusion, then reuse the existing reranker.
  - A **routing rule**: expand only when the question contains entity tokens or relational intent.
  - A relational slice in the evaluation set.
- **New skills:** rank fusion and retrieval evaluation, both needed anyway. **Ops burden:** none new.
- **Failure modes:**
  - Expanded context adds noise and **hurts single-hop questions** (§2.1), hence routing and reranking.
  - **ACL leakage** if an expanded item's audience scope is not re-checked before the prompt.
  - A latency creep of tens of milliseconds.
- **Effort:** +1.5–3 engineer-weeks, including the gold set. **Value:** a likely but unproven lift on "who/what/which-client" multi-hop questions. Literature effects are **+2 to +10 points** on multi-hop and negative on fact lookup when unrouted.
- **Use cases covered:** adds 6 (multi-hop recall Q&A). An optional companion is **per-client rolling summaries** for 7 (§5.4).

### Option D — Full GraphRAG and/or Neptune Analytics / Bedrock KB GraphRAG — **later / optional**

- **What you build:**
  - LLM entity and relation extraction over all mail, chats and transcripts
  - cross-extraction entity resolution
  - community detection
  - LLM community reports
  - global map-reduce search
  - incremental re-indexing on every new message and every deletion

  The managed alternative is Bedrock KB GraphRAG (S3 documents → Neptune Analytics) or Neptune Analytics with the awslabs graphrag-toolkit.
- **New services or skills:**
  - Neptune Analytics: openCypher, capacity sizing, snapshots.
  - GraphRAG pipeline tuning.
  - A **second data store** to secure, back up, purge and keep consistent with Postgres.
  - India residency workarounds.
- **Ops burden:** high. Per-tenant graphs cost at least **$350–403/month each**. Re-index jobs run continuously, and DSAR purges reach into summaries that blend many sources.
- **Failure modes:**
  - **Indexing cost**, estimated at $170–750+ per user one-off (§7).
  - **Stale, hard-to-purge summaries.**
  - **Judge-inflated gains** (§2.1).
  - **No managed GraphRAG in either India region.**
  - **Isolation only via metadata filters** on a shared graph (§6).
  - The **Microsoft GraphRAG library is "largely in maintenance mode"** (its README, Oct 2026).
- **Effort:** 8–16+ engineer-weeks to production quality, plus ongoing operations [Low]. **Value for us now:** low. Our "global" questions are already scoped by keys we know (a client, a quarter), and the cheaper per-client summaries in §5.4 cover them. **Real value** appears only for a tenant-wide relationship-intelligence add-on (use case 8, §11).

### Decision

| | A. Columns | **B. Postgres graph** | C. + GraphRAG-lite | D. Full GraphRAG / Neptune |
|---|---|---|---|---|
| Complexity (1–5) | 1 | **2** | 3 | 5 |
| Extra effort | 0 | **+1–2 eng-wk** | +1.5–3 eng-wk | 8–16+ eng-wk + ops |
| New AWS service | No | **No** | No | Yes (Neptune; Bedrock KB) |
| LLM cost added | $0 | **$0** | ≈ $0.2–0.7/user-mo (extra context) | ≈ $170–750+/user one-off + monthly |
| Unlocks | Drafting relationships, ledger v0, scoping | **+ one-query exclusion closure, brief context, ledger links, base for C** | + multi-hop recall Q&A | + corpus-wide summaries; tenant-wide analytics |
| When | MVP fallback | **MVP** | **v1.5, if §8 passes** | Later / optional, on §9 triggers |

**Plain recommendation:** build **B**, keep it metadata-only, and add **C** in v1.5 only if it passes §8. Treat **D** as later or optional. If B threatens the MVP date, ship **A** and backfill B later; nothing is lost.

---

## 4. Use-case verdicts

| # | Use case | Graph justified? | Columns suffice? | Why | When |
|---|---|---|---|---|---|
| 1 | Per-recipient relationship type and per-person style (user → contact) | **No** | **Yes**: `relationships` row per user × contact; style slices keyed by relationship × intent × channel × language | A single-hop lookup with many attributes, which is a table's job. R05's schema already does it. | MVP |
| 2 | Org chart / reporting lines (Entra manager chains) | **No** | **Yes**: `manager_token` column + recursive CTE (measured **0.6 ms** chain, **2.8 ms** for a 999-person subtree). Graph returns the whole chain via `$expand=manager($levels=max)` (R01 §C). | Trees are the textbook recursive-CTE case | MVP |
| 3 | Commitments ledger across email, Teams and meetings (owner → counterparty → client → evidence) | **No** (B makes it uniform) | **Yes**: `commitments` table with owner, counterparty and client tokens plus evidence pointers; "what do I owe Acme?" = one join through `works_at` | Ledger questions are filters and aggregates, which suit SQL (TimelineQA, R05 §5.4) | MVP (email + chat); v1.5 (+ meetings) |
| 4 | Client/account scoping closure: "exclude Acme" ⇒ its people, threads, chats, meetings, atoms | **Graph-shaped query, not a graph DB** | **Yes**, with scope tags enforced at ingest and in vector filters; B turns the retro-purge into one closure query (**37 ms p50; 55 ms for the biggest client**) | The closure is 3 hops over known edge types; enforcement belongs in code and filters, not traversal | MVP |
| 5 | Entity resolution across channels (SMTP, Entra ID, transcript speaker label, nicknames) | **No** | **Yes**: vault tokens are the canonical IDs; alias rows plus reversible `same_as` edges for later merges | Resolution happens once in the vault (R10 §6.7). A graph DB adds nothing to it. | MVP (vault); v1.5 (speaker labels) |
| 6 | Multi-hop recall Q&A; pre-meeting briefs (2-hop neighbourhood of attendees) | **Yes, lightly** (retrieval step C on B) | Briefs: **yes** (deterministic SQL, **1.7 ms p50**). Multi-hop Q&A: columns + vectors are the baseline; GraphRAG-lite *may* add **+2–10 points** on relational questions | The literature's most consistent graph win is multi-hop. Our seeds are free (tokens), so expansion is cheap. | v1.5, gated (§8) |
| 7 | "Sensemaking" questions ("what's going on with Acme this quarter?") | **Not GraphRAG.** Use **per-client summaries** | **Yes**: scope by client token + time window, then map-reduce over atoms and thread summaries | GraphRAG's community detection discovers groups we already know (clients, projects, meeting series). Its cost, purge and maintenance problems are avoidable. | v1.5 (optional, gated) |
| 8 | Tenant-level relationship intelligence (who in our firm knows whom at the client, warm paths, strength) | **Eventually, at enterprise scale** | **Initially yes**: a consented, metadata-only aggregate table (internal user, external token, strength, last contact); warm paths = 2-hop self-join | Only whole-graph algorithms (centrality, communities, >3-hop paths) at tenant scale outgrow SQL. That is the Neptune Analytics trigger (§9). | Phase 2–3, as a paid add-on |

---

## 5. Recommended design (option B now, C in v1.5)

### 5.1 Phases

| Phase | What the product ships | Graph work | Extra LLM cost |
|---|---|---|---|
| **MVP** (weeks 1–12) | Relationship-aware drafts, commitments ledger v0, client/account scoping, user exclusions | **B:** two tables (§5.2), MVP edge types only, filled from metadata in the same transaction as the source row. About six SQL functions. The closure query backs purges and the impact preview. **No GraphRAG, no graph DB.** | $0 |
| **v1.5** (months 4–6) | Teams meeting memory, recall Q&A, pre-meeting briefs (Pro) | `attendee` and `about` edges from the **existing** atom extractor. Brief builder on B (§5.4). **C (GraphRAG-lite, §5.3) behind the §8 gate.** Optional per-client summaries (§5.4). | ≈ $0.2–0.7/user-month for C; ≈ $0.5–1 for summaries [Low] |
| **Phase 2** (months 6–12), *later / optional* | Better "what changed?" and multi-hop answers | Validity ranges on more edge types. *Optional:* HippoRAG-2-style Personalized PageRank over one user's subgraph in app memory, only if C plateaus. Graphiti-style temporal facts only if R05 §7.11's trigger fires. | Small |
| **Later**, *optional* | Enterprise relationship intelligence (use case 8) | Consented, metadata-only tenant aggregate in **Postgres first**; Neptune Analytics per enterprise tenant only on §9 triggers | Infra from $350/month per tenant |

### 5.2 Minimal schema (Postgres property graph)

Two tables, the same row-level security as every other table, and **no free text**: entity keys are vault tokens or our own item IDs (§10).

```sql
-- One row per entity *per user*: the same client appears once in each user's graph.
CREATE TABLE graph_node (
  tenant_id     uuid   NOT NULL,
  owner_user_id uuid   NOT NULL,
  node_id       bigint GENERATED ALWAYS AS IDENTITY,
  kind          text   NOT NULL,  -- self | person | org | thread | chat | meeting | atom | commitment
  entity_key    text   NOT NULL,  -- vault token ('PERSON_k3d9', 'CLIENT_9f2') or item ID ('thr_…', 'ep_…', 'atm_…')
  degree        int    NOT NULL DEFAULT 0,  -- refreshed nightly; used to skip hubs
  last_seen     timestamptz,
  PRIMARY KEY (tenant_id, owner_user_id, node_id),
  UNIQUE (tenant_id, owner_user_id, kind, entity_key)
);

CREATE TABLE graph_edge (
  tenant_id     uuid   NOT NULL,
  owner_user_id uuid   NOT NULL,
  src           bigint NOT NULL,
  dst           bigint NOT NULL,
  etype         text   NOT NULL,  -- catalogue below
  last_ts       timestamptz NOT NULL,       -- most recent supporting event
  weight        real   NOT NULL DEFAULT 1,  -- e.g. number of supporting messages
  valid_from    timestamptz,                -- only for facts that change (works_at, reports_to)
  valid_to      timestamptz,
  PRIMARY KEY (tenant_id, owner_user_id, src, etype, dst),
  FOREIGN KEY (tenant_id, owner_user_id, src) REFERENCES graph_node ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, owner_user_id, dst) REFERENCES graph_node ON DELETE CASCADE
);
CREATE INDEX graph_edge_out ON graph_edge (tenant_id, owner_user_id, src, etype, last_ts DESC) INCLUDE (dst);
CREATE INDEX graph_edge_in  ON graph_edge (tenant_id, owner_user_id, dst, etype, last_ts DESC) INCLUDE (src);
-- ALTER TABLE … ENABLE / FORCE ROW LEVEL SECURITY; policy on tenant_id + owner_user_id (R04).
```

**Edge catalogue.** Every content-derived edge touches an *item* node (thread, chat, meeting, atom or commitment). Deleting the item therefore deletes its edges by cascade (§10).

| `etype` | From → to | Filled from | Phase |
|---|---|---|---|
| `works_at` | person → org | Verified domains → client org; Entra for internal staff; user confirmation | MVP |
| `reports_to` | person → person | Entra `manager` (R01 §C) | MVP |
| `participant` | person → thread / chat | From/To/Cc headers; chat roster (no body text) | MVP |
| `owed_by`, `owed_to`, `for_client` | commitment → person / person / org | Commitments-ledger extractor (already planned) | MVP |
| `evidence` | atom or commitment → thread / chat / meeting | Evidence pointers the extractors already write | MVP (ledger); v1.5 (atoms) |
| `attendee` | person → meeting | Calendar attendees; named transcript speakers | v1.5 |
| `about` | atom → person / org | Atom subject, speaker and assignee tokens (R05 §7.12) | v1.5 |
| `same_as` | person → person | Vault merges; speaker-label resolution, with provenance; reversible | v1.5, optional |

**Deliberately left out:**
- **The user's relationship to each contact** stays in R05's `relationships` table, with its many style columns. It is not copied into edges.
- **"Thread is about client X"** is computed by a 2-hop query (participants → `works_at`) instead of being stored.
- **Bi-temporal record-time columns** stay on memory atoms (R05 §4.5). Edges carry only `valid_from`/`valid_to` where facts change.
- **Free text, embeddings and LLM-extracted entities** never enter these tables.

### 5.3 GraphRAG-lite: graph-expanded hybrid retrieval (v1.5 only, behind §8)

This plugs into the AgentCore `search_memory` tool and the brief builder. Drafting's hot path does not use it.

1. **Parse.** The existing R05 §5.4 parser (Haiku) extracts the time window, event references, atom types and answer shape.
2. **Pick seeds, deterministically.** Seeds are entity tokens already present in the L1 question (`⟦CLIENT_9f2⟧`), the attendees of a resolved meeting, and in drafting the current thread's recipients. Cap at 5.
3. **Route.** With no seeds and no relational intent (who, with, owe, promised, client), **skip expansion** and run plain hybrid retrieval. This avoids the single-hop losses in §2.1.
4. **Expand** in one SQL query:
   - 1 hop from each seed, plus 2 hops only along typed paths (org → person → item; person → item → atom);
   - cap at 50 neighbours per seed by `last_ts`, within the parsed time window if there is one;
   - skip the `self` node and nodes whose `degree` exceeds a hub threshold (start at 500);
   - stop at 200 candidate items.
5. **Post-filter.** Drop every candidate item that is in the live exclusion set or fails the request's audience ACL. This is the **same post-filter applied to vector hits** (R12 E7; §10).
6. **Gather evidence.** Pull the candidates' L1 chunks and atoms from Postgres. In parallel, run the normal S3 Vectors top-k (time pre-filter) and Postgres full-text top-k.
7. **Fuse** with reciprocal-rank fusion: `score = Σ 1/(60 + rank_list)` over the vector, full-text and graph lists. The graph list is ranked by hop distance, then recency. Integration of graph and plain retrieval was the most reliable hybrid in Han et al. (+6.4%).
8. **Rerank** the top 50 down to 8–12: Cohere Rerank 3.5 in the US; Haiku in India, which has no Bedrock rerank (R03).
9. **Answer.** Cite every claim, abstain without evidence, and attach a small "who is who" card from the graph (role, organisation, last contact; tokens only, re-hydrated at render).

Step 4 is the benchmark's `q7` query (3.6 ms p50). It uses `LATERAL (… ORDER BY last_ts DESC LIMIT 50)` per seed, in and out edges, then a second capped hop.

### 5.4 Briefs and per-client summaries (v1.5)

- **Pre-meeting brief.** For each attendee, deterministic SQL on B collects:
  - the `relationships` row (type, strength, last-tone label);
  - the last five threads or meetings;
  - open commitments in both directions;
  - open requirements and questions from atoms about their client in the last 90 days.

  One LLM call then writes the brief from this structured context, with citations. Measured database time is **1.7 ms p50**, and **5.3 ms** for the six most connected people.
- **Per-client rolling summaries: "community reports without community detection"** (*optional, gated*).
  - **Inputs:** each week, per user and per active client, the atoms and thread summaries scoped by the client token and time window. These come from the closure / 2-hop query.
  - **Output:** a short report with citations. Its lineage is the list of contributing item IDs, so the purge job regenerates it whenever any item is excluded or deleted (≤ 24 h).
  - **Why not GraphRAG:** GraphRAG's Leiden step exists to *discover* communities. Ours (clients, projects, meeting series) are known keys.
  - **Cost:** about **$0.5–1/user-month** at 20 active clients, assuming 8k tokens in and 600 out per summary on Haiku [Low].

### 5.5 Measured performance (local micro-benchmark, 9 Oct 2026)

**Setup:**
- PostgreSQL **16.2**, local, on an Intel i7-1355U laptop with 16 GB RAM; `shared_buffers` 512 MB; warm cache.
- **10 users** in one table with **FORCE RLS** on `owner_user_id`; each user has **50,001 nodes and 281,088 edges**.
- Power-law contact skew: the most connected contact has 9,355 thread/meeting edges, and the biggest client has 200 people.
- A `self` hub is linked to all 27,000 threads and meetings.
- Covering indexes in both directions.
- pgbench: 500 runs per query (100 for the heaviest), with a random user and seed each run. The data is synthetic.

| Query (one user's graph) | p50 | p95 |
|---|---|---|
| 1-hop: people at a client | 0.31 ms | 0.64 ms |
| 2-hop: recent threads/meetings with people at a client (90 days, top 50) | 1.12 ms | 1.98 ms |
| 3-hop: … → atoms and commitments citing them | 1.66 ms | 3.02 ms |
| Brief context, 6 random attendees | 1.72 ms | 2.77 ms |
| Brief context, 6 most connected people | 5.34 ms | 9.37 ms |
| **GraphRAG-lite capped expansion, 3 seeds** | **3.62 ms** | **7.62 ms** |
| Manager chain (recursive CTE) | 0.58 ms | 0.94 ms |
| Whole 999-person reporting subtree (recursive) | 2.84 ms | 4.48 ms |
| **Full exclusion closure, random client** | **36.6 ms** | **47.1 ms** |
| Full exclusion closure, biggest client (191 people → 3,693 threads/meetings → 3,020 atoms/commitments) | 55.1 ms | 87.7 ms |
| Uncapped recursive 3-hop walk (worst case) | 16.6 ms | 33.1 ms |

**Under load** (8 concurrent clients):

| Query | Throughput | p95 |
|---|---|---|
| 2-hop | ≈ 6,400 queries/s | 1.7 ms |
| GraphRAG-lite | ≈ 1,600 queries/s | 7.5 ms |
| Briefs | ≈ 4,100 queries/s | 2.7 ms |

**Storage:** 521 MB for all 10 users including indexes, about **52 MB per heavy user**.

**Caveats [Med]:** this ran on a laptop, not Aurora. Aurora Serverless v2 at low ACU has fewer vCPUs, a cache miss reads from network storage, and each call adds about 1–2 ms of round trip. **Repeat this on Aurora with production-shaped data in the week-1 spike.** Even with a 10× penalty, every interactive query stays under about 100 ms.

---

## 6. AWS and Postgres options checked (October 2026)

| Option | Verified facts | Fit for PersonaAgent | Conf. |
|---|---|---|---|
| **Neptune Analytics** | **Price** (Price List, published 11 Sep 2026): **$0.48/h per 16 m-NCU** in us-east-1 and us-west-2 (= **$0.03 per m-NCU-hour; $350.40/month** minimum graph); **$0.552/h** in ap-south-1 (**$402.96/month**); **not priced in ap-south-2**. 1 m-NCU = 1 GB memory. Sizes run from **16 to 24,576 m-NCU**.<br>**Stop/start:** launched Aug 2025; a stopped graph bills **10%** ($0.048/h US). Snapshots cost $0.021/GB-month (US).<br>**Features:** openCypher, with algorithms as `CALL neptune.algo.*`: BFS and shortest paths, PageRank, degree, closeness, eigenvector centrality, Jaccard, WCC, SCC, label propagation, **Louvain and Leiden**.<br>**Limits:** **one vector index per graph**, fixed at creation, 1–65,535 dimensions; vector updates are not atomic. Worker threads = m-NCU / 4, so a 16 m-NCU graph serves 4 queries at once. | Over-provisioned for per-user graphs. Plausible later per **enterprise** tenant for whole-graph algorithms. Its India DR is a rebuild after failover. | High |
| **Neptune Database Serverless** | **$0.1608/NCU-h** (US), **$0.1848** (Mumbai), **$0.17688** (Hyderabad). Capacity runs from **1.0 to 128 NCU**, where 1 NCU ≈ 2 GiB; it does not scale to zero. Minimum ≈ **$117/month** per instance. Storage $0.10/GB-month (US) or $0.11 (India); I/O $0.20–0.22 per 1M. | A second database to run, with no row-level security. No advantage over Aurora at our sizes. | High |
| **Bedrock KB GraphRAG** (GA 7 Mar 2025) | **Regions: Frankfurt, London, Ireland, Oregon, N. Virginia, Tokyo, Singapore. Not Mumbai or Hyderabad.**<br>**Graph:** lexical (chunk → document, entity → chunk), built by Claude 3 Haiku (Legacy), Claude Haiku 4.5 or Nova. Some of these models run only through **cross-Region inference profiles**.<br>**Limits:** **S3 is the only data source**; **no graph-build customisation**; no autoscaling of the Neptune graph; **1,000 files per data source** (raisable to 10,000).<br>**Retrieval:** vector search, then traversal. Metadata filters exist, but the docs do not say whether they constrain the *traversal* step. | Unusable for India tenants. Per-user isolation would need one knowledge base and one graph per user, or filters of unverified reach. Feeding it means copying L1 text into S3 files. | High (docs); unverified (traversal scoping) |
| **awslabs graphrag-toolkit** (lexical-graph **v3.19.1**, 26 Aug 2026; Apache-2.0) | **Graph stores:** Neptune Database, Neptune Analytics, Neo4j; FalkorDB is mentioned. **Vector stores:** Neptune Analytics, OpenSearch Serverless, **Postgres pgvector**, **S3 Vectors**.<br>**Postgres is a vector store only, not a graph store.**<br>Graph model: Source → Chunk → Topic → Statement → Fact → Entity.<br>Tenancy is a label/index prefix (1–25 characters). There is no documented isolation guarantee and no tenant deletion. | Useful reference design. Adopting it means adopting Neptune. | High |
| **AgentCore Memory** | Built-in strategies: **semantic, user preference, summary, episodic**, plus overrides and self-managed. **No graph or knowledge-graph strategy.** | No change to R05: use it only for the assistant's own chat memory | High |
| **Postgres graph extensions** | **Apache AGE is absent** from the Aurora PostgreSQL extension lists for versions 12–18 and from RDS lists for 16–19. **pgrouting** (3.6–3.8) and **ltree** are present. **SQL/PGQ** (`GRAPH_TABLE`) was committed for PostgreSQL 19 in March 2026, then **reverted in Beta 4** (24 Sep 2026): "Revert SQL/PGQ (property graph query) support." | Plain SQL (joins, `LATERAL`, recursive CTEs) is the path. Re-check SQL/PGQ for PostgreSQL 20. | High |
| **Microsoft GraphRAG library** | v3.3.0 released 8 Oct 2026. The README says it is **"largely in maintenance mode, and won't be accepting new PRs or implementing new features"** and warns that "indexing can be an expensive operation". | Vendor risk if adopted as a dependency | High |

**Region availability for graph services** (✔ = priced or listed; Price List Sep 2026 and Bedrock docs, Oct 2026):

| Service | us-east-1 | us-west-2 | ap-south-1 (Mumbai) | ap-south-2 (Hyderabad) |
|---|---|---|---|---|
| Aurora PostgreSQL Serverless v2 (graph-in-tables) | ✔ | ✔ | ✔ | ✔ |
| Neptune Analytics | ✔ $0.48/h | ✔ $0.48/h | ✔ $0.552/h | **✘** |
| Neptune Database Serverless | ✔ $0.1608 | ✔ $0.1608 | ✔ $0.1848 | ✔ $0.17688 |
| Bedrock KB GraphRAG | ✔ | ✔ | **✘** | **✘** |

---

## 7. Cost comparison at 1k and 10k users

**Assumptions** (all [Low] unless marked):
- **A1. Tenants.** Average tenant is 100 seats, so 1k users = 10 tenants and 10k users = 100 tenants. At 50 seats, per-user Neptune costs double.
- **A2. Graph size.**
  - Heavy user: 50k nodes / 281k edges, which is **52 MB in Postgres** including indexes (measured, §5.5). Postgres storage below uses this heavy figure, to be conservative.
  - Typical user: about one third of that (≈ 94k edges).
  - Neptune memory: assumed ≈ 150 bytes per edge for a metadata-only graph, unverified.
- **A3. Query load.** 100 graph queries per user per workday × 22 days, at about 3 ms of database time each (measured range 0.3–8 ms).
- **A4. Unit prices** [High]:

  | Item | US | Mumbai |
  |---|---|---|
  | Aurora storage | $0.10/GB-month | $0.11/GB-month |
  | Aurora compute | $0.12/ACU-h | $0.18/ACU-h |
  | Neptune Analytics | $0.03/m-NCU-h | $0.0345/m-NCU-h |
  | Haiku 4.5, batch (R03) | $0.50/M in, $2.50/M out | — |
  | Haiku 4.5, on-demand (R03) | $1/M in, $5/M out | — |

- **A5. GraphRAG corpus.** 150k messages × 250 tokens = **37.5M tokens per user**, matching R03's backfill assumption.

| Option | 1k users (10 tenants) | 10k users (100 tenants) | Per user-month | Notes |
|---|---|---|---|---|
| **B/C: graph-in-tables in Aurora** | **≈ $10/month** (storage $5.20, I/O ≈ $4, compute < $1) | **≈ $100/month** | **≈ $0.01** (India ≈ $0.015) | Uses the cell's existing Aurora; no new fixed cost |
| Per-tenant **Neptune Analytics**, metadata graph (16 m-NCU fits A2) | $3,504/month (India $4,030) | $35,040/month (India $40,296) | **$3.50** (India $4.03) | **≈ 8×** R04's whole per-user infrastructure budget (≈ $0.44). Doubles with an HA replica (replica billing unverified). Stopping graphs out of hours roughly halves it, but cold-start time is unverified. |
| Per-tenant Neptune Analytics with **in-graph vectors** (Bedrock KB GraphRAG style; 100 users × 150k 1,024-d vectors ≈ 61 GB → 64 m-NCU) | $14,016/month | $140,160/month | **≈ $14** (India ≈ $16) | Bedrock KB GraphRAG keeps chunk embeddings in the graph |
| **Shared** Neptune Analytics graph per cell (32–64 m-NCU at 1k; 128–256 at 10k) | ≈ $700–1,400/month | ≈ $2,800–5,600/month | ≈ $0.28–1.40 | **Disqualified.** One KMS key and one vector index for all tenants, no row-level security, application-side isolation only. Breaks invariant 6 in `02-solution-architecture.md` ("one tenant, one key, one index"). |
| Neptune Database Serverless per tenant (2–4 NCU realistic) | ≈ $2,350–4,700/month | ≈ $23,500–47,000/month | ≈ $2.35–4.70 | The 1 NCU minimum ($117/month) gives only 2 GiB of memory |
| **Full GraphRAG indexing** (LLM extraction, any store) | **≈ $170k–750k+ one-off** | **≈ $1.7M–7.5M+ one-off** | plus ≈ $6–25 ongoing | **Dominates every infrastructure line** (below) |
| C's extra answer context (+1–3k tokens per Q&A; 220 Q&A per user-month; Haiku) | ≈ $220–660/month | ≈ $2.2k–6.6k/month | ≈ $0.2–0.7 | The only material cost of option C |

**How the GraphRAG indexing estimate is built:**
- **Bottom-up.** 62.5k chunks of 600 tokens × (2.1–3.1k input + 0.4–0.8k output tokens) × 1–2 extraction passes × 1.33 for summaries and community reports. Microsoft puts extraction at about 75% of indexing cost, hence the 1.33. On Haiku batch this gives **≈ $170–590 per user**.
- **Cross-check 1.** LazyGraphRAG puts full GraphRAG indexing at about 1,000× vector-RAG indexing. Our embedding backfill is $0.75 per user (R03), so ≈ **$750**.
- **Cross-check 2.** HippoRAG 2 measured GraphRAG at 115.5M input / 36.1M output tokens for 11,656 passages. Scaled to 150k messages, that is ≈ **$1,900**.
- **Ongoing cost** assumes 150k messages ≈ 30 months of history, plus community-report regeneration. The LightRAG paper estimates GraphRAG's report regeneration at about 1,399 × 2 × 5,000 tokens per update on its Legal corpus.

**Bottom line:** the graph *pattern* costs about **a cent per user-month**. A graph *database* costs **$3.50–14 per user-month**. Full GraphRAG costs **4–18 months of a $40 seat** before it answers a single question.

---

## 8. Evaluation gate: what must improve before C (or summaries) ship

**Gold set.**
- **Size:** ≥ **300 questions** from ≥ **20 dogfood or design-partner users**, US and India, built from R05 §5.6's weekly question collection.
- **Labels:** each question carries gold evidence IDs and a type.

  | Type | Share | Example |
  |---|---|---|
  | Single-hop fact | 30% | |
  | **Multi-hop relational** | 25% | "what did anyone at ⟦CLIENT_9f2⟧ ask me to send after the March review?" |
  | Temporal / "what changed" | 20% | |
  | List / aggregate | 10% | |
  | Sensemaking | 10% | |
  | Should-abstain | 5% | |

- **Exclusions:** no gold item may come from an excluded source (R12 X8).

**Arms:**
- **0.** MVP hybrid retrieval: vector + full-text + SQL filters + rerank.
- **1.** C with routing.
- **2.** C always on, run to measure harm.
- **3.** For sensemaking only: per-client summaries vs on-the-fly map-reduce over the same scoped atoms.

**Debiased judging** (because of §2.1, Zeng et al.):
- human-verified answers on a 20% sample;
- the LLM judge sees both answer orders, with a length-matched prompt and 3 trials;
- **a self-vs-self sanity run must land near 50/50** before any result counts.

**Ship C only if all of these hold:**

| # | Criterion | Threshold (proposed) |
|---|---|---|
| G1 | Multi-hop relational accuracy vs arm 0 | **+≥ 8 pp absolute** (95% CI excludes 0) **or** ≥ 25% relative error reduction |
| G2 | No regression elsewhere | No question type drops > **2 pp**; overall ≥ **+2 pp** |
| G3 | Evidence recall@10 on relational questions | **+≥ 10 pp** |
| G4 | Citation precision / abstention | Citation precision stays ≥ **0.95**; abstention correctness no worse |
| G5 | Latency | End-to-end p95 **+≤ 300 ms**; expansion query p95 ≤ **50 ms on Aurora** at production size |
| G6 | Cost and safety | **+≤ $0.003 per query**; **zero** new failures in the contextual-integrity (T6) and exclusion-canary suites (release-blocking) |

**Ship per-client summaries only if:**
- blinded, debiased preference is ≥ **60%** against on-the-fly map-reduce;
- **claim-level faithfulness ≥ 0.95**, meaning every claim cites an atom or span;
- regeneration completes within 24 h of any source exclusion or deletion;
- cost is ≤ **$1/user-month**.

**Consider D (full GraphRAG, Graphiti or Neptune) only if** C has shipped and the failure analysis still shows ≥ **15%** of relational or "what changed" questions failing *because structure is missing* (R05 §7.11's trigger), **and** a paying driver exists (§9). If C fails G1–G3, record the result and stop. That is a valid outcome: plain hybrid retrieval wins and the graph stays a SQL convenience.

---

## 9. Triggers for ever moving to Neptune

Move a workload to **Neptune Analytics, one graph per enterprise tenant**, only when **T1 and at least one of T2–T4** hold:

| # | Trigger | Concrete signal |
|---|---|---|
| **T1** | **A paying driver** | A tenant-wide relationship-intelligence add-on (use case 8) is sold to ≥ 2 enterprise tenants or a signed design partner. Each tenant's revenue clears a **5%-of-revenue** infrastructure test: a $350/month graph needs ≈ $7k/month of tenant revenue, about **145–175 seats** at $40–49. |
| **T2** | **Algorithms SQL can't serve** | The product needs whole-graph centrality or PageRank, Louvain/Leiden communities, or warm paths beyond 2 hops through external intermediaries, at interactive latency |
| **T3** | **Performance on Aurora** | After indexes, caps and hub suppression, required traversals exceed **p95 300 ms** at production size, *or* graph jobs miss their nightly window, *or* graph work exceeds **≈ 20% of cell Aurora CPU** |
| **T4** | **Quality** | The §8 failure analysis shows misses fixable only by algorithms that are impractical in Postgres (for example tenant-scale PPR), and C has already shipped |

**Pre-conditions before the first Neptune graph:**
1. **Postgres stays the system of record.** Neptune holds a *projection* rebuilt from Postgres. Nodes and edges are exported as CSV to a per-tenant S3 prefix and bulk-loaded. Deletions propagate inside the same ≤ 24 h purge SLA (§10).
2. **One graph per tenant**, encrypted with that tenant's key. Never a shared graph (§7).
3. **India.** Mumbai is fine at $0.552/h. **Hyderabad has no Neptune Analytics**, so India DR for the feature is "rebuild from S3 after failover" and is stated in contracts. Don't route around this with Bedrock KB GraphRAG, which is absent from both India regions.
4. **Cost controls.** Use **stop/start** (10% billing) for batch-only analytics graphs. Size by the `GraphStorageUsagePercent` metric, and keep vectors in S3 Vectors rather than the graph unless measured otherwise.

**Non-triggers.** None of these alone justifies Neptune:
- "GraphRAG is popular";
- one customer asking for "a knowledge graph" with no workload behind it;
- multi-hop failures that C has not yet been tried on.

---

## 10. Redaction tokens, per-user isolation, exclusion purges and the US/India cells

**Tokens are the entity keys (R10 §6.7).**
- `graph_node.entity_key` is the vault token's type and ID (`PERSON_k3d9`, `CLIENT_9f2`). It is **never** a name, email address or phone number. Surface-form variants (`.first`, `.full`, `.nick`) map to the same node, and names are re-hydrated only at render.
- **Tier-R identifiers never become nodes**; they are masked irreversibly at first touch. **Tier-S content creates no `about` edges.**
- **Never-send placeholders (`⟦NS_id⟧`) are not entities.** They never become nodes or labels. A Tier-P token the vault marks `ns=true` keeps its node, but graph-derived cards never re-hydrate it unless the user allowed it (R12 §9.6).
- **Entity resolution happens once, in the vault.** The vault clusters aliases from directory data and headers. The graph only records later merges as reversible `same_as` edges with provenance; for example, transcript "Speaker 2" is resolved to `PERSON_k3d9`. Queries follow `same_as` for one hop.
- **No cross-tenant linkage.** Tokens are random and per tenant, so the same human in two tenants has unrelated keys. This keeps CPRA's "no combining data across customers" by construction.

**Per-user isolation.**
- Every node and edge row carries `tenant_id` and `owner_user_id` under **FORCE ROW LEVEL SECURITY**. The benchmark ran with RLS on. The same client is a separate node in each user's graph, so **no query can traverse into a colleague's mail**.
- Expansion results (§5.3 step 5) pass the **same audience-ACL post-filter as vector hits** before any prompt. A "who is who" card inherits the strictest audience scope of its evidence.

**Exclusion purges.** The graph follows the exclusion engine; it never decides scope itself.

Facts from R12 and `02-solution-architecture.md` §6.5:
- **Rules:** rules target a person, address, domain, chat, thread, or meeting/series, and are keyed by an HMAC of the identifier. Tenant and user rules combine, and **any exclusion wins**.
- **Purge mechanics:** purge is **driven by lineage**, because S3 Vectors has no delete-by-filter (`DeleteVectors` by key, ≤ 500 per call) and query filters allow ≤ 100 conditions. So **the app post-filters every hit**.
- **Targets:** logical exclusion **≤ 1 min**; physical purge **≤ 24 h**. A legal hold defers only the physical purge.

What the graph adds to that design:
1. **At ingest.** Excluded items are never fetched (R12 X1–X2), so they never create nodes or edges.
2. **Logical exclusion (≤ 1 min).** GraphRAG-lite and the brief builder apply the live exclusion post-filter to every expanded item, exactly as for vector hits. *Graph traversal is not a side door.*
3. **Physical purge (≤ 24 h).** The purge job deletes the **item nodes named in lineage**, and `ON DELETE CASCADE` removes their edges. A nightly orphan scan removes nodes left with no edges, such as an excluded external person, and refreshes `degree`. Per-client summaries whose lineage includes a purged item are regenerated, and brief caches are invalidated.
4. **Preview cross-check.** The closure query (§5.5: 37–55 ms per user) recomputes the impact of a person or domain rule from the graph. A mismatch with the header-index count raises an alert. Lineage stays authoritative.
5. **Semantics match R12.** Excluding a person removes the *conversations they are in*, not mentions elsewhere. `about` edges from atoms in surviving conversations therefore remain, and the never-send list covers names.
6. **Tenant client scoping** ("exclude Acme") uses the same rule engine (domain rules plus the org token). The graph needs no client-specific code.
7. **Why full GraphRAG is a deletion hazard.** Community reports blend many sources, so deleting one source means regenerating reports (§7). For Bedrock KB GraphRAG, deletion means removing the S3 document and re-syncing; whether the graph is cleaned up is unverified. Lineage-tracked per-client summaries avoid both problems.

**US and India cells.**
- B and C use only services every cell already has: Aurora, S3 Vectors and in-region Bedrock models. They work the same in us-east-1, us-west-2, ap-south-1 and ap-south-2.
- In the India cell, the rerank step and any summaries run on Haiku 4.5 `in.`, so processing stays in India.
- Any Neptune feature is US- and Mumbai-only, with a rebuild-on-failover DR story (§9).
- Bedrock KB GraphRAG is unavailable in India. Even in US regions, its graph-construction models may run through cross-Region profiles, which conflicts with tenant residency promises.

**Tenant-level relationship intelligence (later)** deliberately crosses per-user isolation, so it is a **governance decision before an engineering one**. It requires:
- a separate, consented aggregate holding counts and strength scores only, with no content, subjects or never-send terms;
- an admin policy and employee notice;
- per-user opt-out;
- excluded sources never contributing;
- legal review of purpose limitation under DPDP and CPRA (R07).

---

## 11. Monetisation evidence: relationship intelligence (use case 8)

| Vendor | How it is sold | Price | Conf. |
|---|---|---|---|
| **Affinity** (relationship-intelligence CRM for dealmakers) | Core product. Every plan has automatic email and calendar capture; "relationship scoring: see the warmest path to any contact"; Scale adds inferred network connections | **$2,000 / $2,300 / $2,700 per user per year** (Essential / Scale / Advanced), billed annually; Enterprise custom | High (pricing page) |
| **Salesforce Einstein Relationship Insights** | A separate product line with its own editions (relationship graphs, research assistant) | **$50 (Starter) / $150 (Growth) per user per month**, billed annually | High (pricing page) |
| **Microsoft Dynamics 365 Sales "who knows whom"** | The basic version comes free from Dynamics data. The **enhanced, Exchange-based version needs specific Sales licences** and server-side sync. | Sales Premium is reported at **$135–150 per user per month** (secondary sources conflict) | High (feature/licensing doc); Med–Low (price) |
| **Introhive** (targets law, accounting and consulting firms) | Enterprise contracts | No public price. Vendr reports a **median ≈ $36k per year** (range $19k–47k). A third-party per-seat estimate of $150–400 per month does not reconcile with that. | Low–Med |
| **4Degrees** | Per user per month | "Get pricing" only | — |

**What this means:**
- **Buyers pay for this.** The prices sit at **$50–225 per user per month**, mostly in professional services and dealmaking. That overlaps our IT-services and consulting beachhead.
- **It is a different product from ours.** It needs firm-wide aggregation (§10) and competes with CRM incumbents. Microsoft gives away a basic version inside Dynamics.
- **The sensible path:**
  1. Ship *per-user* relationship value in Pro: briefs, relationship history and the commitments ledger, built on B and C.
  2. Test a **tenant-wide add-on** with design partners as an *Enterprise option*. Price it as an add-on hypothesis, for example **+$10–20 per user per month** [Low; our hypothesis, unvalidated].
  3. Only then evaluate Neptune against §9.

---

## 12. Open questions / could not verify

**Unverified this session:**
1. **Neptune Analytics sizing.** Not verified: memory per edge and node (§7 assumes ≈ 150 B per edge), replica billing, and how long a stopped graph takes to start.
2. **Bedrock KB GraphRAG.** Not verified:
   - whether metadata filters constrain the *graph-traversal* step or only the first vector search (the docs are silent);
   - extraction quality on token-pseudonymised text (untested);
   - whether graph nodes are cleaned up when a source document is deleted.
3. **LazyGraphRAG** is confirmed only inside Microsoft Discovery and Azure Local (June 2025 note). Availability in the open-source library is unverified.
4. **"Does Memory Need Graphs?" acceptance at ACL 2026** rests on a university news page seen only in search results. The arXiv page lists no venue.
5. **GraphRAG-Bench token table.** Its global-search figure (~331k tokens per query) conflicts with its own prose (~40k). The intro's secondary claims (13.4% lower NQ accuracy, a 16.6% drop on time-sensitive questions, 2.3× latency) were not checked at source and are not used in this report.
6. **WildGraphBench:** abstract only; no numbers used.
7. **Prices.** Introhive and 4Degrees publish none. Dynamics 365 Sales Premium is reported at $135 or $150 by different secondary sources. Whether Salesforce ERI needs Sales Cloud is unclear. Database Savings Plans coverage of Neptune Analytics remains unverified (carried over from R04).
8. **PostgreSQL 19 final release notes** were not checked (GA expected in October 2026). SQL/PGQ "can potentially be included in a later major release".
9. **The full-GraphRAG indexing estimate** (§7) is derived, not measured. It depends on chunking, prompts, gleaning passes and prompt caching.

**Open questions for our own measurement:**
- **Aurora re-run.** Repeat the §5.5 benchmark on Aurora Serverless v2 (0.5–4 ACU, cold and warm cache, RLS on), with production-shaped data from dogfood tenants.
- **Hub threshold.** Find the right cut-off (500 is a starting guess) and decide whether degree should count recent edges only.
- **India.** Does GraphRAG-lite help Hinglish and Indian-English questions as much as US-English ones? Report §8 results per language slice.
- **Speaker resolution.** What share of Teams transcript speakers resolve to Entra-linked tokens? This decides how much `same_as` work v1.5 needs (R02 and R05 open items).
- **Purge time.** How much does edge cascade add to purge time at tenant scale? The ≤ 24 h SLA should hold easily: the closure for the biggest client took 55 ms.

---

## 13. Sources

All sources were accessed 9–11 Oct 2026. ✔ marks a primary source fetched this session; ○ marks a source seen only in search results or a secondary source.

**Graph RAG research**
- ✔ Edge et al., "From Local to Global: A Graph RAG Approach to Query-Focused Summarization" (v2, 19 Feb 2025): https://arxiv.org/abs/2404.16130 · https://arxiv.org/html/2404.16130v2
- ✔ LazyGraphRAG (Microsoft Research blog, 25 Nov 2024; editor's note 6 Jun 2025): https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/
- ✔ GraphRAG indexing methods (Standard vs FastGraphRAG): https://microsoft.github.io/graphrag/index/methods/
- ✔ microsoft/graphrag README (maintenance-mode note; v3.3.0, 8 Oct 2026): https://github.com/microsoft/graphrag
- ✔ Guo et al., LightRAG (v3, 28 Apr 2025): https://arxiv.org/abs/2410.05779 · https://arxiv.org/html/2410.05779v3
- ✔ Gutiérrez et al., HippoRAG 2, "From RAG to Memory" (ICML 2025): https://arxiv.org/abs/2502.14802 · https://arxiv.org/html/2502.14802v2
- ✔ Han et al., "RAG vs. GraphRAG: A Systematic Evaluation and Key Insights" (v3, 4 Mar 2026): https://arxiv.org/abs/2502.11371 · https://arxiv.org/html/2502.11371v3
- ✔ Xiang et al., "When to use Graphs in RAG" / GraphRAG-Bench (v3, 22 Feb 2026; ICLR 2026): https://arxiv.org/abs/2506.05690 · https://arxiv.org/html/2506.05690v3 · https://mlanthology.org/iclr/2026/xiang2026iclr-use/
- ✔ Zeng et al., "How Significant Are the Real Performance Gains? An Unbiased Evaluation Framework for GraphRAG" (v2, 13 Aug 2026): https://arxiv.org/abs/2506.06331 · https://arxiv.org/html/2506.06331v2
- ✔ Wang et al., WildGraphBench (2–3 Feb 2026; abstract only): https://arxiv.org/abs/2602.02053

**Agent memory**
- ✔ Rasmussen et al., Zep: A Temporal Knowledge Graph Architecture for Agent Memory (Jan 2025): https://arxiv.org/html/2501.13956v1
- ✔ Chhikara et al., Mem0 / Mem0g (Apr 2025): https://arxiv.org/html/2504.19413
- ✔ Hu et al., "Does Memory Need Graphs?" (v3, 10 Feb 2026): https://arxiv.org/abs/2601.01280 · https://arxiv.org/html/2601.01280v3
- ✔ Wu et al., "Memory in the LLM Era: Modular Architectures and Strategies in a Unified Framework" (v3, 6 Aug 2026): https://arxiv.org/abs/2604.01707 · https://arxiv.org/html/2604.01707v3

**AWS and Postgres**
- ✔ AWS Price List API, AmazonNeptune (published 11 Sep 2026), files for us-east-1, us-west-2, ap-south-1 and ap-south-2: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonNeptune/current/region_index.json
- ✔ Amazon Neptune pricing (m-NCU = 1 GB; paused graphs bill 10%): https://aws.amazon.com/neptune/pricing/
- ✔ Neptune Analytics docs:
  - overview: https://docs.aws.amazon.com/neptune-analytics/latest/userguide/what-is-neptune-analytics.html
  - algorithms: https://docs.aws.amazon.com/neptune-analytics/latest/userguide/algorithms.html
  - vector index: https://docs.aws.amazon.com/neptune-analytics/latest/userguide/vector-index.html
  - stopping a graph: https://docs.aws.amazon.com/neptune-analytics/latest/userguide/managing-stopping.html
  - GraphRAG metadata-filter best practices: https://docs.aws.amazon.com/neptune-analytics/latest/userguide/best-practices-graphrag-filters.html
- ○ Neptune Analytics stop/start launch (Aug 2025): https://aws.amazon.com/about-aws/whats-new/2025/08/amazon-neptune-stop-start-capability/
- ✔ Neptune Serverless capacity scaling (1.0–128 NCU): https://docs.aws.amazon.com/neptune/latest/userguide/neptune-serverless-capacity-scaling.html
- ✔ Bedrock Knowledge Bases GraphRAG:
  - regions and limits: https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-build-graphs.html
  - graph-construction models: https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-build-graphs-build.html
  - querying and filters: https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-neptune.html
  - GA blog (7 Mar 2025): https://aws.amazon.com/blogs/machine-learning/announcing-general-availability-of-amazon-bedrock-knowledge-bases-graphrag-with-amazon-neptune-analytics/
- ✔ awslabs graphrag-toolkit (lexical-graph v3.19.1, 26 Aug 2026):
  - repository: https://github.com/awslabs/graphrag-toolkit
  - lexical-graph README: https://raw.githubusercontent.com/awslabs/graphrag-toolkit/main/lexical-graph/README.md
  - graph model: https://raw.githubusercontent.com/awslabs/graphrag-toolkit/main/docs-site/src/content/docs/lexical-graph/graph-model.mdx
  - storage model: https://raw.githubusercontent.com/awslabs/graphrag-toolkit/main/docs-site/src/content/docs/lexical-graph/storage-model.mdx
  - multi-tenancy: https://raw.githubusercontent.com/awslabs/graphrag-toolkit/main/docs-site/src/content/docs/lexical-graph/multi-tenancy.mdx
- ✔ AgentCore Memory strategies: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-strategies.html · https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/built-in-strategies.html
- ✔ Aurora PostgreSQL supported extensions (no `age`): https://docs.aws.amazon.com/AmazonRDS/latest/AuroraPostgreSQLReleaseNotes/AuroraPostgreSQL.Extensions.html
- ✔ RDS for PostgreSQL supported extensions (no `age`): https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-extensions.html
- ✔ PostgreSQL 19 Beta 4 (24 Sep 2026; "Revert SQL/PGQ"): https://www.postgresql.org/about/news/postgresql-19-beta-4-3386/
- ✔ Local benchmark: PostgreSQL 16.2 binaries from the `pgserver` 0.1.4 wheel (PyPI). Scripts were kept in the session scratchpad and are not part of the repo; §5.5 describes the method.

**Relationship-intelligence market**
- ✔ Affinity pricing: https://www.affinity.co/pricing
- ✔ Salesforce Einstein Relationship Insights pricing: https://www.salesforce.com/sales/einstein-relationship-insights-pricing/
- ✔ Dynamics 365 Sales "who knows whom" (updated 29 May 2026): https://learn.microsoft.com/en-us/dynamics365/sales/who-knows-whom
- ○ Dynamics 365 Sales Premium price (secondary, conflicting): https://www.aguidetocloud.com/licensing/dynamics-365-sales-premium/ · https://www.costbench.com/software/crm/microsoft-dynamics/
- ○ Introhive contract values (Vendr, secondary): https://www.vendr.com/marketplace/introhive
- ✔ 4Degrees pricing (no public prices): https://www.4degrees.ai/pricing

**Internal cross-references:**
- R01 §C (Entra manager chain)
- R03 §8 (Bedrock prices, backfill assumptions)
- R04 §2.4, §3.6 and §9 (Neptune options, regions, cost floors)
- R05 §4, §5, §7.11 and §7.12 (memory benchmarks, atoms, v2 graph trigger, schemas)
- R10 §6.7 (tokenisation vault)
- R12 §7 and §9 (exclusions and purge)
- `02-solution-architecture.md` §6.5 and §8
