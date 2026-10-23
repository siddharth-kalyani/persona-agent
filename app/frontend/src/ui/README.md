# Vanimo UI: the design system in practice

Premium and professional, never decorative. Research behind it (2026-10-23): Linear's 2024 and 2026
refreshes, Vercel Geist, Stripe, Raycast, Attio, Superhuman, Fluent 2, Primer, Carbon, Atlassian,
Apple HIG, Emil Kowalski and Rauno Freiberg on motion.

## Rules

1. **Neutral first, one accent.** Warm greys carry ~95% of the screen. Deep teal (`brand`) is only for
   the one primary button per view, links, focus, selection and progress. No gradients, glows, glass,
   sparkles, emoji or "AI" badges anywhere.
2. **Hierarchy from type and space, not boxes.** A page is `Page` (one h1) → `Section`s (h2), spaced
   32–40px apart. Use `Surface` (1px border, 12px radius, no shadow) only for a self-contained object:
   the email you're replying to, a draft, a tile you can select. Never nest surfaces, never wrap a whole
   section in a card "for structure".
3. **Lists are rows, not cards.** `List` + `ListRow`: hairline-separated, 40px single line or two-line
   (title + meta), hover fill, selected = neutral fill + thin accent bar. Row actions on the right.
4. **Type scale** (`typo`): pageTitle 22/28, sectionTitle 16/24, itemTitle 14/20 (500), body 14/20,
   reading 15/24 (drafts, emails, transcripts, answers), meta 13/18, label 12/16, metric 28/32. Weights
   400/500/600 only. Sentence case everywhere: no UPPERCASE labels. `typo.tabular` for compared numbers,
   `typo.mono` only for literal machine data (tokens like `⟦PERSON_3fa2c1d0⟧`, IDs, versions),
   `typo.address` for email addresses and domains.
5. **Colour tokens.** Prefer Fluent `tokens.*` (our theme maps them): `colorNeutralBackground1` surface,
   `colorNeutralBackground2` frame, `colorNeutralBackground3` inset, `colorNeutralStroke2` border,
   `colorNeutralStroke3` hairline, `colorNeutralForeground1/3/4` text. Use `vt.*` for what Fluent lacks
   (`accentTint`, `successTint`/`warningTint`/`dangerTint`, diff colours, `dot`). Every `vt` value
   has a light fallback, so components also render inside the Outlook add-in and Teams (which keep
   Microsoft's own themes). Never hard-code hex in pages. Light and dark must both work.
6. **Status never by colour alone.** `StatusDot` and `Pill` always carry a word. Pills are neutral
   unless the state needs attention (`warning`, `danger`), `success` for a finished good outcome,
   `accent` for "selected/active".
7. **Loading.** `PageSkeleton` for a page's first load and `RowsSkeleton` inside a section (both appear
   only after 300ms, so fast loads never flash). Spinners only inside the button or row doing the work.
   Long AI work (learning, drafting, probes) shows a `StepList` in plain words.
8. **Empty states** (`EmptyState`) say what will appear and how to get it, with one action. No jokes or
   illustrations.
9. **Messages.** Fluent `MessageBar` for anything the user must read or act on (errors, warnings,
   blocking checks), placed where it applies, never animated. Keep success confirmations inline and
   short.
10. **Motion** (`theme/motion.ts`): colour-only hover (100ms), `Rise` (fade + 4px, 200ms) for content
    that appears because of a user action (a draft, an answer, a finished step). Nothing animates on
    keyboard actions, sorting, numbers, errors or blocking warnings. Reduced motion is respected.
11. **Dates** via `Time` (relative, exact on hover) or `relativeTime` / `absoluteTime`.
12. **Responsive.** Works at 1280px laptops and down to 360px phones: no horizontal page scroll, two
    columns collapse to one below ~760px, tables become stacked rows, long addresses wrap
    (`overflowWrap: "anywhere"`).
13. **Accessibility.** One h1 per page, ordered headings, visible focus (Fluent's ring, recoloured to the
    accent), labels on icon-only buttons, 24px minimum targets (44px on touch).
14. **Copy.** Plain and specific ("3 drafts are waiting for you"), sentence case, no hype.
