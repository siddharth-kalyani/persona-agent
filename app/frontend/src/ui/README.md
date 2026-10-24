# Vanimo UI: the design system in practice

**Calm precision.** A professional work tool in the family of Linear, Vercel, Stripe and Attio: layered
surfaces, crisp hairlines, a cool neutral palette with one teal accent, colour only where it carries
meaning, and icons as the first thing the eye scans. No gradients, glows, glass, sparkles, emoji,
illustrations or "AI" badges. Motion only where it explains a change.

Second pass (2026-10-24). It replaces the first pass's "no boxes, type and space only" rule, which read
as bland, especially in dark mode.

## Surfaces (elevation)

| Level | What | Token |
| --- | --- | --- |
| Frame | app background, sidebar | `vt.frame` |
| Panel | the inset content panel each page sits on | `vt.surface` |
| Card | `Surface`, `List bordered`, `DataTable`, stat cards, `Section variant="card"` | `tokens.colorNeutralBackground1` (= `vt.card`) + `vt.border` + `vt.shadowCard` |
| Raised | menus, popovers, dialogs, tooltips | `vt.raised` + `vt.shadowRaised` |
| Well | quoted text, transcripts, code, wells inside a card | `vt.inset` |

Dark mode is layered, not inverted. Surfaces get lighter as they rise (frame #0A0B0D → card #15161A →
raised #1C1D21), borders are low-alpha white, and cards carry a faint top highlight instead of a shadow.
Never put a card inside a card. Use a well (`vt.inset`) or a hairline instead.

## Colour

- **Neutrals carry the page.** Cool greys, defined in `theme/theme.ts`. Text: `vt.text1` (primary),
  `vt.text2` (secondary), `vt.text3` (tertiary, ≥4.5:1 on every surface except a selected row).
- **One accent (teal)** for the primary button, links, focus, the selected nav icon, progress and
  "active/selected" chips.
- **Tones** for `Pill` and `IconTile`:
  - `neutral`.
  - `accent`.
  - Categories: `blue` (email), `purple` (Teams chat), `accent` (meetings).
  - States: `success`, `warning`, `danger`.

  Tints are soft backgrounds with a strong foreground. Never use a tone just to decorate.
- Never hard-code hex in pages; use `tokens.*` or `vt.*`. Every `vt` value has a light fallback, so
  shared components still render inside the Outlook add-in and Teams (Microsoft's themes).

## Icons

Fluent System Icons only (`@fluentui/react-icons`): `Regular` everywhere, `Filled` for the selected nav
item and for status glyphs.

- Sizes: 16 inside buttons, rows, pills and inputs; 20 in the nav and in `IconTile`s of 32px or more.
- **`IconTile`** (a rounded tinted square) leads:
  - the page header (automatic, from the nav icon);
  - stat cards;
  - section and card headers;
  - list rows that represent an object: an email (`Mail`, blue), a Teams chat (`Chat`, purple), a
    meeting (`CalendarLtr`, accent), a commitment (`TaskListSquareLtr`);
  - empty states.

  People get a `PersonAvatar` instead: initials on a soft tint, the tint fixed per address.
- **Icons replace words** where the icon is unambiguous and the action repeats: done ✓, snooze, dismiss ✕,
  copy, delete, refresh, expand, thumbs up/down, open. Use `IconAction`: an icon-only button that always
  has a tooltip and an aria-label. Keep icon + text for the one primary action per view and for actions an
  icon can't say on its own ("Put in my Drafts folder").
- Metadata reads as icon + value: `Clock` 3 h ago, `People` 3 recipients, `Mail` email, `Globe`
  external. Don't write "Email · to your team · 12 words" as a sentence of dots.
- Status pills may carry a 16px icon (`Clock` for due, `ClockAlarm` for overdue, `Globe` for external,
  `PlugDisconnected` for the offline stand-in).
- **Exceptions, not repetition.** Mark what differs (Excluded, Overdue), not the normal state on every
  row. A list under an "Overdue" header shows the date as danger text rather than one red pill per row,
  and "Used" is a quiet dot. Say "Offline stand-in" once per page (`EngineBadge` in the header actions).

## Type (`typo`)

Inter Variable, optical sizes on. Weights 400/500/600, sentence case, no UPPERCASE.

| Token | Size/line | Use |
| --- | --- | --- |
| pageTitle | 24/32 600, -0.022em | h1, one per page |
| sectionTitle | 15/22 600 | h2 |
| cardTitle | 14/20 600 | card and panel headers |
| itemTitle | 14/20 500 | row titles |
| body | 14/20 | |
| reading | 15/24 | drafts, emails, transcripts, answers |
| meta | 13/18 | secondary lines |
| label | 12/16 500 | pills, table headers, group labels |
| metric | 28/34 600, tabular | stat values |
| mono | 12.5/18 | literal machine data only (`⟦PERSON_…⟧`, IDs) |

- `typo.tabular` wherever numbers are compared.
- `typo.address` for email addresses and domains.

## Building blocks (`src/ui`)

- `Page`: icon tile (automatic) + h1 + a **one-sentence** description + actions (one primary).
  - Longer explanations go in an `InfoTip` beside the title, not in a paragraph.
  - No per-page "Sample workspace" pill: the sidebar shows the workspace.
- `Section`: an h2 header (optional `icon`, `count`, `info`, `actions`) above its content.
  - `variant="card"` puts the header inside a card with a hairline under it (use on dashboards: Home,
    Diagnostics, Redaction checks).
- `Surface`: a card.
- `List` / `ListRow`: rows inside a card (`List bordered`).
  - Layout: leading `IconTile` or `PersonAvatar`, a title, a meta line (icons welcome), and trailing pills,
    time or `IconAction`s.
  - Selected row: neutral fill + accent bar.
- `StatStrip` + `Stat`: separate stat cards, each with an `icon` tile, a label, a big value and an
  optional `hint` (`hintTone` for overdue counts).
- `Pill` (tones above, optional `icon` or `dot`), `StatusDot`, `EngineBadge` (offline stand-in vs
  Claude on Bedrock, with the explanation in a tooltip).
- `IconTile`, `IconAction`, `PersonAvatar`, `InfoTip`, `Meter` (a thin proportion bar for percentages
  such as greeting share or progress).
- `EmptyState`: icon tile, title, one sentence, one action.
- `DataTable`: dense admin and settings data; it stacks on phones.
- `Segmented`: a real segmented control (inset track, raised selected segment) with counts.
- Fluent components (buttons, inputs, menus, dialogs, tooltips, message bars) are restyled app-wide in
  `theme/styleHooks.ts`. Don't restyle them per page.

## Motion

- Colour-only hover (100ms).
- `Rise` (fade + 4px, 200ms) for content that appears because of a user action.
- The page fade on navigation.

Nothing else. Nothing animates on keyboard actions, sorting, numbers, errors or blocking warnings.
Reduced motion is respected.

## Layout and responsiveness

- **Widths:** Page widths reading 760, normal 1080, wide 1280.
- **Spacing:** 32px between sections, 12–16px inside cards.
- **Breakpoints:** works from 1280px laptops down to 360px phones, with no horizontal page scroll. Two
  columns collapse below ~900px, tables stack below 640px, and long addresses wrap.

## Accessibility

- **Field borders:** fields keep one even hairline with an accent edge and halo on focus. Their resting
  border is under 3:1. That trade-off is deliberate: every field has a visible label, and in dark mode
  its own recessed fill. Selects show an accent border on keyboard focus.
- **Announcements:** pre-send checks are announced when they appear (blocking ones at once).
  `InfoTip` takes focus when it opens.
- **"Show all":** a toggle ("Show fewer"), so keyboard focus never drops.

- **Structure:** one h1 and ordered headings.
- **Focus:** a visible focus ring (accent).
- **Icon-only controls:** an aria-label and a tooltip.
- **Status:** never shown by colour alone; a pill always has a word, and an icon tile in a row is
  decorative (`aria-hidden`) because the row's text says what it is.
- **Contrast:** AA for all text tokens (checked with a script).
- **Targets:** 24px minimum, 44px on touch.

## Copy

- **Tone:** plain and specific, sentence case, no hype.
- **Length:** one sentence under a title; detail in `InfoTip`.
- **Safety statements stay visible where they matter.** "Vanimo never sends" belongs beside the draft
  actions.
