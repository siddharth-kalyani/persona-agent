# AI memory & recorder wearables — fact sheet (hardware track, Section C)

> Produced 2026-10-05 by a hardware-track research sub-agent. Method: WebFetch on primary pages only (WebSearch budget already exhausted), fetched 2026-10-05. WebFetch paraphrases pages via a small model, so wording may be approximate; vendor-page facts are vendor claims. The Verge could not be fetched. "Unverified (memory)" = memory only, do not cite.

## 1. Limitless (formerly Rewind AI)
| Claim | Numbers/dates | Source | Conf. |
|---|---|---|---|
| Meta acquired Limitless | announced Dec 5, 2025; price undisclosed | https://techcrunch.com/2025/12/05/meta-acquires-ai-device-startup-limitless/ ; https://www.limitless.ai/ | High |
| Team destination | Reality Labs wearables (Ray-Ban Meta, Oakley Meta) | TechCrunch | High |
| Funding / founders | >$33M from a16z, First Round, NEA; Dan Siroker (ex-Optimizely CEO) & Brett Bejcek; began as Rewind ~5 years earlier | TechCrunch | High |
| Pendant price | $99 | TechCrunch | High |
| Sales stopped | "no longer selling the Pendant as of December 5, 2025" | limitless.ai | High |
| Existing customers | supported "for at least another year"; subscription fees dropped — everyone moved to Unlimited free | limitless.ai; TechCrunch | High |
| Regional cut-off | service ended Dec 5, 2025 in Brazil, China, EU, Israel, South Korea, Turkey, UK; data download until Dec 19, 2025 (14 days) | limitless.ai | High |
| Desktop capture ended | Limitless Desktop/Web recording stopped; Rewind app "sunsetting", capture disabled Dec 19, 2025 | limitless.ai | High |
| Export/delete | "delete your Limitless account or export your Limitless data at any time" | limitless.ai; https://help.limitless.ai/ | High (vendor) |
| Apr 2024 rebrand/Pendant launch; pre-acquisition plan prices; Teams/SOC 2/HIPAA offering; 2026 Meta integration | — | — | Unverified |

Inference: pendant owners should expect support to end ~Dec 2026 ("at least a year"). Customers in cut-off regions were effectively bricked with two weeks' notice → strong evidence for "no-brick" and data-escrow promises.

## 2. Bee (now Amazon)
| Claim | Numbers/dates | Source | Conf. |
|---|---|---|---|
| Amazon acquisition | announced Jul 22, 2025 (LinkedIn post by co-founder Maria de Lourdes Zollo; Amazon confirmed to TechCrunch); not closed at the time; terms undisclosed; staff offered Amazon jobs | https://techcrunch.com/2025/07/22/amazon-acquires-bee-the-ai-wearable-that-records-everything-you-say/ | High |
| Pre-deal pricing | $49.99 bracelet + Apple Watch app; $19/month subscription | TechCrunch | High (Jul 2025) |
| Funding | $7M in 2024 (investors unnamed; Exor-led from memory) | TechCrunch | High / investors unverified |
| Privacy policy | audio "not saved, stored, or used for AI training"; user-profile data stored | TechCrunch citing Bee policy | High (stated) |
| Oct 2026 status | still sells Bee Pioneer $49.99 (20% discount banner); "ships only to the United States", "iOS only"; footer "©2026 Amazon.com, Inc." | https://www.bee.computer/ | High |
| Specs | up to 7 days (160 h) battery; dual mics with noise filtering; 40 languages; modular wristband/clip; "A single press of the button starts and stops capturing"; LED "green when Bee is capturing and off when it is not" | bee.computer | High (vendor) |
| Developer access | Bee CLI exports conversations/facts/todos to local markdown; MCP server ("Connect Claude, Claude Code, or Codex"); "Bee Skill" (E2E encrypted); real-time streaming & local HTTP proxy; no documented audio access or rate limits | https://docs.bee.computer/ | High (vendor) |
| Alexa+ integration, CES 2026 news, current subscription price, India availability | — | — | Unverified (site ships US-only) |

## 3. Plaud — the clearest commercial success
| Claim | Numbers/dates | Source | Conf. |
|---|---|---|---|
| Traction | "Trusted by over 2.5 million professionals globally"; App Store 4.9; Trustpilot 4.7 (2,000+ reviews); G2 4.6 | https://www.plaud.ai/ | High (claim) / Med (independent) |
| Lineup (Oct 2026) | Note Pro; Plaud One (pre-order, "For getting Plaud agent to work by voice"); Note; NotePin S; NotePin; Plaud Desktop | plaud.ai | High |
| Device prices | ~$159 (Note, NotePin), ~$179 (Note Pro, NotePin S) | — | Unverified (memory) |
| Individual AI plans | Starter free 300 min/mo; Pro $17.99/mo or $8.33/mo annual, 1,200 min/mo; Unlimited $29.99/mo or $19.99/mo annual, "up to 24 hours/day"; add-on packs 600/3,000/6,000 min; 112+ languages; GPT, Gemini, Claude models; Zapier | https://www.plaud.ai/pages/plaud-ai-plan-pricing | High |
| Team plan | annual $20/user/mo launch offer until Nov 30, 2026 then $25; monthly $28 then $35; unlimited minutes; central billing, seat mgmt, device mgmt (assign/reassign), offboarding, workspace-level data residency, priority support; volume device discounts | https://www.plaud.ai/pages/plaud-team ; https://www.plaud.ai/pages/bulk-order | High |
| Infrastructure | AWS in US, Europe, Singapore, Japan — no India region listed; encryption in transit/at rest; no training without opt-in; DPA in commercial terms | Team page | High (vendor) |
| Enterprise gaps | Team page doesn't mention SSO, SCIM, audit logs, retention policies | Team page | Med |
| Compliance badges | SOC 2 (Type II on pricing page), HIPAA, GDPR, ISO 27001, ISO 27701, EN 18031 | plaud.ai; pricing; https://www.plaud.ai/pages/trust | Med (vendor; reports not reviewed) |
| **Third-party developer platform** | Device SDK (iOS 14+, Android 5.0+) with built-in BLE pairing; apps can start/stop/monitor recordings and get audio files; Transcription API with diarization in 112 languages; end users don't need a Plaud subscription — developer "pay[s] for transcription usage and the number of connected devices"; supports Note Pro & NotePin S; separate MCP + CLI for account data | https://dev.plaud.ai/ ; https://docs.plaud.ai/documentation/plaud_app/mcp | High (vendor) |
| Revenue/units/funding/profitability (~1M units, ~$250M ARR 2025 from memory) | — | — | Unverified — do not cite |
| Why it worked | verified: one clear job (record & summarise meetings), monetised by minutes; memory-only: vibration-conduction call recording, long battery, credit-card form factor | mixed | mixed |
| India | no India-specific content or INR pricing found | plaud.ai | High (absence) |

## 4. Omi (Based Hardware)
| Claim | Numbers/dates | Source | Conf. |
|---|---|---|---|
| What it does | "2nd brain" that "captures your screen and conversations"; real-time transcripts, summaries, action items; "fully open source", MIT; 13.6k GitHub stars, 2.6k forks | https://github.com/BasedHardware/omi | High |
| Stack | pendant firmware on nRF + Zephyr (C) (exact chip unstated; nRF52840 from memory); Omi Glass dev kit on ESP32-S3 with camera; BLE; Flutter mobile app; Swift macOS app; Python/FastAPI/Firebase backend | GitHub | High |
| Price | $129 limited-time (regular $179) one-time; Free: "Unlimited on-phone + 300 cloud min/month"; Unlimited $29.99/mo or $269.91/yr | https://www.omi.me/pages/product | High (vendor) |
| Specs | 10–14 h battery; 2 mics; Bluetooth + Wi-Fi; 2.5 × 1.5 cm; iOS 15+, Android 7+, Mac, web | omi.me | High (vendor) |
| Security claims | "SOC 2 + HIPAA compliant"; TLS + AES-256; "run Omi locally" | omi.me | Low–Med (unaudited) |
| Users | "300,000+ professionals" | GitHub; omi.me | Med (vendor) |
| Business plans, LED, mute switch | none on product page | omi.me | Med |
| CES 2025 "brain interface", founder Nik Shevchenko, earlier $89/dev-kit prices | — | — | Unverified (memory) |

## 5. Friend (Avi Schiffmann)
| Claim | Numbers/dates | Source | Conf. |
|---|---|---|---|
| Domain | friend.com bought for $1.8M (~¾ of $2.5M raised) | https://en.wikipedia.org/wiki/Avi_Schiffmann citing https://www.theverge.com/2024/7/30/24207029/friend-ai-companion-gadget and https://www.404media.co/ai-friend-company-spent-1-8-million-and-most-its-funds-on-domain-name/ | High |
| Price | $129 (Sept 2025); $99 at Jul 2024 launch from memory | https://techcrunch.com/2025/09/27/ai-startup-friend-spent-more-than-1m-on-all-those-subway-ads/ | High / $99 unverified |
| NYC subway campaign | Sept 2025: >$1M on 11,000+ car cards, 1,000 platform posters, 130 urban panels | TechCrunch | High |
| Founder | "a huge gamble"; "I don't have much money left" | TechCrunch | High |
| Backlash | ads vandalised ("surveillance capitalism", "get real friends"); Wired "I Hate My AI Friend"; The Atlantic (Oct 6, 2025) called him NYC's "most reviled tech CEO" | TechCrunch; Wikipedia citing https://www.theatlantic.com/technology/2025/10/friend-ai-companion-ads/684451/ | High / Med |
| How it works | always-listening neck pendant; replies via phone text | Wikipedia | Med |
| Sales, ship dates, valuation (~$50M memory), 2026 status | friend.com renders only "friend" | — | Unverified |

## 6. Sandbar Stream ring
| Claim | Numbers/dates | Source | Conf. |
|---|---|---|---|
| Product | "private voice ring"; touch-activated mic, "not always listening"; glass touchpad (hold/tap/swipe), haptics, aluminium-resin, "all-day" rechargeable battery, USB-C; notes/todos, chat (web, memory, voice), dictation into any app on iOS & Mac | https://www.sandbar.com/ | High (vendor) |
| Price/plan | $249 pre-order (regular $349); free tier (notes, music, weekly dictation); "Data Plan" $10/mo for pre-order members (unlimited dictation, voice chat, memory); pre-orders include 3 months | https://shop.sandbar.com/ | High |
| Shipping/terms | "Batch 5: Shipping Mid-Dec, Limited Quantities" (year unstated); batches 1–4 sold out; US first; 30-day returns; 1-year warranty; pre-orders refundable | shop.sandbar.com | High (page text) |
| Founders (Mina Fahmi, Kirak Hong, ex-CTRL-labs/Meta), ~$13M raised, Nov 2025 announcement | — | — | Unverified (memory) |

## 7. Pebble / Core Devices — Index 01 ring
| Claim | Numbers/dates | Source | Conf. |
|---|---|---|---|
| Announcement/price | Dec 9, 2025; $75 pre-order rising to $99; no subscription | https://repebble.com/blog/meet-pebble-index-01-external-memory-for-your-brain | High |
| Capture | "only records while the button is pressed"; stores up to 5 min on ring if phone out of range | same | High |
| Battery | silver-oxide, not rechargeable; ~12–15 h total recording or "up to 2 years"; returned to Core Devices for recycling | same | High |
| Processing | on the phone: open-source STT + on-device LLM; encrypted ring-to-phone link; iPhone & Android; open-source app; MCP for custom actions | same | High |
| Schedule slip | promised "beginning in March" 2026 → mass production & first shipments week of Jul 24, 2026; >13,000 pre-orders; most shipped by end Aug, last variants Sept | https://repebble.com/blog/index-01-is-in-mass-production | High |
| Known issues | runs slightly small; mic hole can clog; silicone button wears | same | High |

## 8. Brilliant Labs
| Claim | Numbers/dates | Source | Conf. |
|---|---|---|---|
| Halo specs | $399; Alif B1 (Cortex-M55 + NPU) on-device AI; colour microOLED; 2 bone-conduction speakers; 2 mics with audio-activity detection; low-power optical sensor; BT 5.3; "14 hour" (homepage) / "all-day" (product page) battery; ~40 g; ZephyrOS + Lua; Noa agent "with long-term memory"; free features with daily caps; hardware & software "totally open source" | https://brilliant.xyz/ ; https://brilliant.xyz/products/halo | High (vendor) |
| Halo shipping | "shipments beginning in early August" (year unstated) | product page | Med |
| Price change | $299 at Jul 2025 announcement (memory) vs $399 now | memory vs page | Conflict; $399 current |
| Frame | ~$349 in 2024, open source; not featured now | — | Unverified (memory) |

## 9. Other recorders (unverified leads only)
Anker Soundcore Work, Mobvoi TicNote, HiDock (H1/P1), Viaim RecDot, Taya.

## Enterprise readiness at a glance (M365, US + India, work-only buyer)
| Vendor | Team/admin | Compliance claims | SDK/export | India |
|---|---|---|---|---|
| Plaud | Team plan $20–35/user/mo: seats, device mgmt, residency, billing; no SSO/SCIM/audit logs on Team page | SOC 2 Type II, HIPAA, ISO 27001/27701, GDPR, EN 18031 (vendor) | **Device SDK + Transcription API**, MCP/CLI | no India AWS region listed |
| Omi | none listed | "SOC 2 + HIPAA" (vendor) | MIT open hardware/firmware/app | not stated |
| Bee | consumer only | audio-not-stored policy | CLI, MCP, Skill (no audio) | US-only, iOS-only |
| Limitless | discontinued | — | export only | — |
| Index 01 | none; no subscription | — | open-source app, MCP | ships worldwide |
| Sandbar | none | — | — | US first |

## 10. Cross-device patterns (evidence-based)
1. **One clear job beats a general companion** — Plaud (meetings, minute-based pricing, 2.5M claimed users) thrives; Friend (companion pendant) spent most funding on a domain, met backlash, founder "I don't have much money left."
2. **The market is moving away from always-on capture** — Bee uses a button + green LED; Index 01 records only while pressed; Stream is "not always listening"; Halo uses audio-activity detection. Directly relevant to Pillar 2.
3. **The two best-known always-on pendants were bought by Big Tech in 2025** (Bee → Amazon, Jul; Limitless → Meta, Dec). Limitless stopped sales, cut off 7 jurisdictions with 14 days to export, ended desktop capture → vendor-dependence risk; supports no-brick/escrow promises.
4. **Money is in software, not hardware** — devices $49.99–$399; subscriptions carry the business (Plaud $17.99–$29.99/mo, Omi $29.99/mo, Stream $10/mo, Bee $19/mo pre-acquisition).
5. **Phone-relay over BLE is the norm** — Omi, Index 01, Plaud SDK, Halo use BLE to the phone (Omi adds Wi-Fi); none checked uses its own LTE.
6. **Hardware schedules slip** — Index 01 March → Jul–Sept 2026; Halo shipped ~a year after announcement, with a price rise.
7. **Compliance + team admin opens B2B** — Plaud alone has a Team SKU, compliance badges and a device SDK → "integrate Plaud via its SDK before building our own" is a viable partner-first path.

## Conflicts & uncertainties
Halo price ($299 remembered vs $399 now) and shipping year; Plaud compliance badges on pricing/home pages but not Team page (no audit reports reviewed); Plaud SDK charges for "connected devices" + transcription — unknown whether raw audio can bypass Plaud's cloud (matters for India: no India region); Bee's current subscription & roadmap; Sandbar Batch 5 year and whether batches 1–4 shipped.

## Unverified (memory or not found)
Plaud revenue/units/funding, device prices, vibration-conduction sensor; Limitless pre-acquisition plans, Apr 2024 launch, 2026 Meta integration; Bee investors and Alexa+ plans; Omi CES 2025 claim, founder, chip; Friend launch price, valuation, sales, 2026 status; Sandbar founders & funding; Brilliant Frame status; all of section 9.
