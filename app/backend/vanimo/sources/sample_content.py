"""Message text for the sample workspace (Kestrel Analytics). All invented.

The "you" in this workspace writes with a consistent voice per audience, so style learning has a
real signal to find:
  * manager (Meera) — "Hi Meera,", short, direct, signs off "Thanks, {first}"
  * direct reports — "Hi Rahul," / chat "hey", clear asks ("Please …", "by Friday"), some Hinglish
  * clients — "Dear John," or "Hi Lisa,", formal Indian-English ("PFA", "kindly", "revert"),
    "Best regards,\n{full}"
  * peers — "Hey Vikram,", casual, "Cheers"
  * family — informal, personal

Hard cases for the redaction pipeline are planted on purpose (all numbers are fake but valid
by checksum): an Aadhaar, a PAN, a GSTIN, an IFSC + account number, a UPI ID, a payment card,
a US SSN and routing number, an AWS key, a password, phone numbers — plus never-send material
(the codenames "Project Falcon" and "Operation Monsoon").

Placeholders: {first} / {full} = the signed-in person's sample name.
"""

from __future__ import annotations

# Each script is a list of (who, text). "me" = the signed-in person; "them" = the thread's first
# recipient (or the named address) replying. Order is chronological.
ME = "me"
THEM = "them"

THREAD_SCRIPTS: dict[str, list[tuple[str, str]]] = {
    "Weekly status: Acme replatforming": [
        (
            ME,
            "Hi John,\n\nPFA this week's status for the replatforming. Highlights:\n- Catalogue service migrated to the new cluster; error rate down to 0.2%.\n- Checkout load test is scheduled for Thursday.\n- One open risk: the payment gateway sandbox is still not provisioned on your side.\n\nKindly let us know if the sandbox can be ready by Wednesday so we stay on plan.\n\nBest regards,\n{full}",
        ),
        (THEM, "Thanks {first}. Sandbox should be up Tuesday evening. Can you confirm the cutover window again?"),
        (
            ME,
            "Dear John,\n\nThanks for confirming the sandbox. The cutover window remains Saturday 10 PM to Sunday 4 AM IST. We will share the runbook by Thursday EOD for your review.\n\nBest regards,\n{full}",
        ),
        (THEM, "Perfect. Lisa will join the cutover call from our side."),
        (
            ME,
            "Hi John,\n\nNoted, we will add Lisa to the bridge. I'll revert with the final runbook tomorrow.\n\nBest regards,\n{full}",
        ),
        (
            ME,
            "Dear John,\n\nPFA the final cutover runbook (v1.3). Kindly review the rollback section in particular.\n\nBest regards,\n{full}",
        ),
    ],
    "Re: Acme UAT sign-off": [
        (THEM, "Hi {first}, we found two issues in UAT: the coupon field and the invoice PDF layout."),
        (
            ME,
            "Hi Lisa,\n\nThanks for the detailed list. Rahul is fixing the coupon validation today; the invoice layout fix will be in tomorrow's build. We will request sign-off once both are verified.\n\nBest regards,\n{full}",
        ),
        (
            ME,
            "Hi Lisa,\n\nBoth fixes are deployed to UAT. Kindly re-test and share your sign-off at the earliest.\n\nBest regards,\n{full}",
        ),
        (THEM, "Re-tested, both look good. Signing off."),
        (
            ME,
            "Dear Lisa,\n\nThank you for the quick sign-off. We will proceed with the production release as planned.\n\nBest regards,\n{full}",
        ),
    ],
    "Acme invoice for September": [
        (
            ME,
            "Dear John,\n\nPFA the invoice for September. Bank details for the transfer: HDFC Bank, IFSC HDFC0001234, account number 50100234567891. Our GSTIN is 27AAPFU0939F1ZV.\n\nKindly revert if anything needs correction.\n\nBest regards,\n{full}",
        ),
    ],
    "Project Falcon timeline": [
        (
            ME,
            "Dear Karan,\n\nFollowing our call, PFA the revised Project Falcon timeline. Data migration moves to week 6 so that your team can complete the archival clean-up first.\n\nKindly confirm if this works for the steering committee.\n\nBest regards,\n{full}",
        ),
        (THEM, "Thanks {first}. Week 6 is fine. Can we keep the UAT start date unchanged?"),
        (
            ME,
            "Hi Karan,\n\nYes, UAT stays on 12 November. We will absorb the shift within the build phase.\n\nBest regards,\n{full}",
        ),
        (
            ME,
            "Dear Karan,\n\nA quick update on Falcon: the migration rehearsal on the copy environment completed in 3h 40m, within the 4-hour window.\n\nBest regards,\n{full}",
        ),
        (THEM, "Great news. Please present this at the steering committee."),
        (
            ME,
            "Dear Karan,\n\nWill do. I will include the rehearsal metrics in the steering committee pack.\n\nBest regards,\n{full}",
        ),
        (
            ME,
            "Hi Karan,\n\nGentle reminder on the archival clean-up sign-off from your side; we need it by Friday to keep week 6.\n\nBest regards,\n{full}",
        ),
    ],
    "Re: Falcon data migration risks": [
        (THEM, "Hi {first}, our security team is worried about card data in the legacy tables."),
        (
            ME,
            "Dear Deepa,\n\nUnderstood. We will mask all PAN fields during migration and never move full card numbers. For the test run we only use dummy data such as 4111 1111 1111 1111.\n\nBest regards,\n{full}",
        ),
        (
            ME,
            "Dear Deepa,\n\nPFA the masking design for your security team's review. Kindly revert with comments by Wednesday.\n\nBest regards,\n{full}",
        ),
        (THEM, "Reviewed. Approved with one change on log retention."),
        (
            ME,
            "Dear Deepa,\n\nThank you. We have updated log retention to 30 days as requested.\n\nBest regards,\n{full}",
        ),
    ],
    "FW: Bluefin SOW v3 (Project Falcon)": [
        (
            ME,
            "Hi Meera,\n\nForwarding the SOW v3 from Bluefin. Main change: fixed price for phase 2. Need your approval before I sign.\n\nThanks,\n{first}",
        ),
    ],
    "Bluefin steering committee pack": [
        (
            ME,
            "Dear Karan, Hi David,\n\nPFA the steering committee pack for Thursday. It covers timeline, risks and the migration rehearsal results.\n\nBest regards,\n{full}",
        ),
        (
            ME,
            "Dear Karan,\n\nPFA the minutes from today's steering committee. Action items are on slide 2.\n\nBest regards,\n{full}",
        ),
    ],
    "Orion Health discovery workshop": [
        (
            ME,
            "Dear Emily,\n\nThank you for your time today. PFA the summary of the discovery workshop and the proposed next steps.\n\nBest regards,\n{full}",
        ),
        (
            ME,
            "Hi Emily,\n\nGentle reminder on the list of systems in scope. Once we have it, Priya will start the integration assessment.\n\nBest regards,\n{full}",
        ),
    ],
    "Re: Orion PHI handling questions": [
        (THEM, "How will your team handle PHI during the assessment?"),
        (
            ME,
            "Dear Emily,\n\nOur team will only access de-identified extracts. No PHI leaves your environment, and all access is logged.\n\nBest regards,\n{full}",
        ),
        (
            ME,
            "Dear Emily,\n\nPFA our data handling note for your compliance team. Kindly revert with any questions.\n\nBest regards,\n{full}",
        ),
    ],
    "Please prepare the UAT checklist": [
        (
            ME,
            "Hi Rahul,\n\nPlease prepare the UAT checklist for the billing module and share it by Friday. Loop in Ana for the test data.\n\nThanks,\n{first}",
        ),
        (THEM, "Sure {first}, will share by Thursday itself."),
    ],
    "Re: Leave plan for Diwali week": [
        (THEM, "{first}, please share your team's leave plan for Diwali week."),
        (
            ME,
            "Hi Meera,\n\nRahul is off on 30 and 31 Oct, Ana is around all week. I'll be working remotely on 31st.\n\nThanks,\n{first}",
        ),
        (ME, "Hi Meera,\n\nSmall change: Ana also needs 1 Nov off. Coverage is fine.\n\nThanks,\n{first}"),
    ],
    "Kal ka standup thoda late karte hain": [
        (
            ME,
            "Hi team,\n\nKal ka standup thoda late karte hain, 10:30 instead of 10. Client call clash hai.\n\nThanks,\n{first}",
        ),
    ],
    "Re: Appraisal inputs for Rahul": [
        (THEM, "Please send me your inputs for Rahul's appraisal."),
        (
            ME,
            "Hi Meera,\n\nRahul has done very well this cycle: he owned the coupon engine end to end and mentored two juniors. I'd rate him 'exceeds'.\n\nThanks,\n{first}",
        ),
        (
            ME,
            "Hi Meera,\n\nAdding one point: he also handled the Acme production incident over the weekend.\n\nThanks,\n{first}",
        ),
    ],
    "Hiring: senior data engineer shortlist": [
        (
            ME,
            "Hey Arjun,\n\nShortlisted three profiles for the senior data engineer role. Can you take the technical round for two of them this week?\n\nCheers,\n{first}",
        ),
        (THEM, "Sure, send me the slots."),
        (ME, "Hey Arjun,\n\nSlots: Wed 3 PM and Thu 11 AM. Calendar invites on the way.\n\nCheers,\n{first}"),
        (
            ME,
            "Hey Arjun,\n\nThanks for the feedback. Going ahead with the offer for the second candidate.\n\nCheers,\n{first}",
        ),
    ],
    "Re: Q3 delivery review deck": [
        (THEM, "Please send the Q3 delivery numbers by tomorrow."),
        (
            ME,
            "Hi David,\n\nPFA the Q3 delivery review deck. Utilisation is at 84% and all three key accounts are green.\n\nRegards,\n{full}",
        ),
        (ME, "Hi David,\n\nUpdated slide 4 with the revenue split you asked for.\n\nRegards,\n{full}"),
    ],
    "CloudNest renewal quote": [
        (
            ME,
            "Hi Tom,\n\nThanks for the renewal quote. Before we proceed, kindly share a revised quote with a 3-year term option.\n\nBest regards,\n{full}",
        ),
        (THEM, "Revised quote attached with 3-year pricing."),
        (ME, "Hi Tom,\n\nThanks. We will revert after internal approval this week.\n\nBest regards,\n{full}"),
    ],
    "Fwd: CloudNest outage RCA": [
        (
            ME,
            "Hey Vikram, Arjun,\n\nForwarding CloudNest's RCA for last week's outage. Root cause was a bad config push on their side. Worth checking our failover settings.\n\nCheers,\n{first}",
        ),
    ],
    "Re: Knowledge-transfer plan for Ana": [
        (THEM, "Hi {first}, what should I cover first in the KT?"),
        (
            ME,
            "Hi Ana,\n\nStart with the billing module architecture, then the deployment runbook. Rahul will pair with you for the first two sessions.\n\nThanks,\n{first}",
        ),
        (ME, "Hi Ana,\n\nAlso add the monitoring dashboards to week 2 of the KT plan.\n\nThanks,\n{first}"),
    ],
    "Team lunch on Friday?": [
        (
            ME,
            "Hi all,\n\nTeam lunch on Friday to celebrate the Acme go-live? Thinking 1 PM at the usual place. Let me know!\n\nThanks,\n{first}",
        ),
    ],
    "Re: Weekend plans": [
        (THEM, "Are we going to Lonavala on Saturday?"),
        (
            ME,
            "Yes! Leaving by 7 AM. I've paid the advance on UPI to resort.booking@okaxis. Call me on +91 98765 43210 if anything changes.",
        ),
        (ME, "Also please carry the umbrellas, it's going to rain."),
    ],
    "Operation Monsoon: pricing approach": [
        (
            ME,
            "Hi David, Meera,\n\nFor Operation Monsoon I propose we lead with a fixed-fee pilot and move to T&M after 3 months. Margin stays above 32%.\n\nRegards,\n{full}",
        ),
        (
            ME,
            "Hi David,\n\nUpdated the Monsoon pricing model with the discount scenarios you asked for.\n\nRegards,\n{full}",
        ),
    ],
    "Re: Travel to Pune next week": [
        (THEM, "Hotel needs your ID details for the booking."),
        (
            ME,
            "Hi Neha,\n\nThanks for booking. My Aadhaar for the hotel is 2341 2341 2346 and PAN ABCPE1234F. Please don't forward these.\n\nThanks,\n{first}",
        ),
    ],
    "Re: Security questionnaire for Bluefin": [
        (THEM, "Bluefin's questionnaire asks how we store service credentials."),
        (
            ME,
            "Dear Deepa,\n\nAll service credentials are stored in a secrets manager with rotation every 90 days; nothing is hard-coded. PFA the completed questionnaire.\n\nBest regards,\n{full}",
        ),
        (
            ME,
            "Dear Deepa,\n\nKindly note one correction in section 4: MFA is enforced for all admin accounts.\n\nBest regards,\n{full}",
        ),
    ],
    "Sprint 14 retro notes": [
        (
            ME,
            "Hi team,\n\nRetro notes from today:\n- Keep: daily demo to the client.\n- Change: PR reviews within 4 hours.\n- Try: pairing on flaky tests.\n\nThanks,\n{first}",
        ),
    ],
    # Received only, waiting for a reply (M3 drafting demos).
    "Q4 resource plan before Thursday": [
        (
            THEM,
            "Hi {first},\n\nCan you send me the updated Q4 resource plan before Thursday's review? Also flag if we "
            "need any new hires for the Bluefin ramp-up.\n\nThanks,\nMeera",
        ),
    ],
    "Acme go-live date?": [
        (
            THEM,
            "Hi {first},\n\nOur leadership is asking for the go-live date for the new storefront. Can you confirm "
            "it, and whether the payment gateway work is still on track?\n\nRegards,\nJohn",
        ),
    ],
    "Updated bank details for CloudNest invoice": [
        (
            THEM,
            "Hi {first},\n\nPlease note our bank details have changed. Kindly process the pending CloudNest renewal "
            "payment of USD 18,400 to the new account by today EOD to avoid a service suspension.\n\n"
            "Account: 50100234567891\nIFSC: HDFC0001234\n\nRegards,\nTom Becker\nCloudNest Billing",
        ),
    ],
    # Promises made this week (M5 commitments ledger).
    "Bluefin UAT environment access": [
        (THEM, "Hi {first}, our testers still can't log in to the UAT environment. Who should we talk to?"),
        (
            ME,
            "Dear Karan,\n\nApologies for the delay. I'll share the UAT access list by Friday EOD, and Vikram will confirm the test accounts tomorrow.\n\nBest regards,\n{full}",
        ),
    ],
    "Re: Onboarding checklist for Ana": [
        (THEM, "Hi {first}, is there a checklist for my first two weeks?"),
        (
            ME,
            "Hi Ana,\n\nI will send you the onboarding checklist by Monday. Let me also check the laptop request today.\n\nThanks,\n{first}",
        ),
    ],
}

# Chat histories by sample chat ID. "me" = you; other values are the member's display name.
CHAT_SCRIPTS: dict[str, list[tuple[str, str]]] = {
    "smp-chat-001": [  # 1:1 with Meera (manager)
        ("Meera Iyer", "Can you join the Bluefin call at 4?"),
        (ME, "Yes, joining. Will share the update after."),
        (ME, "Update: Karan is fine with week 6 for migration. SOW v3 needs your approval."),
        ("Meera Iyer", "Thanks, will review tonight."),
    ],
    "smp-chat-002": [  # 1:1 with Rahul (report)
        (ME, "hey Rahul, coupon fix kab tak deploy hoga?"),
        ("Rahul Verma", "Aaj shaam tak, testing chal rahi hai."),
        (ME, "ok, please ping me once it's on UAT"),
        ("Rahul Verma", "Done, it's on UAT now."),
        (ME, "great, thanks!"),
        ("Rahul Verma", "Ek aur cheez, invoice layout ka fix kal ke build mein jayega."),
        (ME, "theek hai, bas sign-off se pehle ek baar UAT pe check kar lena."),
    ],
    "smp-chat-003": [  # 1:1 with Ana (report)
        ("Ana Fernandes", "Hi {first}, do I have access to the billing repo?"),
        (ME, "Raised the request, should be done in an hour. Start with the architecture doc meanwhile."),
    ],
    "smp-chat-004": [  # 1:1 with Vikram (peer)
        ("Vikram Shah", "Did you see the CloudNest RCA?"),
        (ME, "yep, forwarded it. we should test failover next sprint"),
        ("Vikram Shah", "Agreed. Also, the staging DB password is still Kestrel@2026, we need to rotate it."),
        (ME, "please rotate it today and update the vault, thanks"),
        ("Vikram Shah", "Done, rotated and moved to the vault."),
        (ME, "accha hai, thanks yaar"),
    ],
    "smp-chat-005": [  # 1:1 with Priya (peer)
        (ME, "Priya, can you lead the Orion integration assessment?"),
        ("Priya Nair", "Sure, once they send the systems list."),
    ],
    "smp-chat-006": [  # 1:1 with Karan (client, federated)
        ("Karan Malhotra", "Quick one: is the rehearsal on track for Friday?"),
        (ME, "Yes Karan, on track. Will share the metrics by Friday evening."),
    ],
    "smp-chat-007": [  # Delivery leads
        ("Vikram Shah", "Utilisation numbers due today."),
        (ME, "sharing mine in 10 mins"),
        ("Priya Nair", "Mine are in the tracker."),
        (ME, "done, Acme and Bluefin both updated"),
    ],
    "smp-chat-008": [  # Falcon war room
        ("Karan Malhotra", "Migration rehearsal starts at 9 PM tonight."),
        (ME, "Team is ready. Rahul is on the bridge, Vikram is on standby for infra."),
        ("Vikram Shah", "Use the read replica key AKIAIOSFODNN7EXAMPLE for the copy job."),
        (ME, "Vikram please don't paste keys here, move it to the vault. Rehearsal looks good so far."),
        ("Deepa Rao", "Security team is monitoring as well."),
    ],
    "smp-chat-009": [  # All Kestrel India
        ("David Brooks", "Congratulations to the Acme team on the go-live!"),
        (ME, "Thanks David! Great effort by Rahul and Ana."),
    ],
    "smp-chat-010": [  # unnamed group: Rahul, Priya, Ana
        ("Rahul Verma", "Lunch kahan chalein?"),
        (ME, "the usual place? 1 pm"),
        ("Ana Fernandes", "works for me"),
        (ME, "chalo phir, 1 baje neeche milte hain"),
        ("Priya Nair", "Main thoda late aaungi, 10 min."),
        (ME, "koi baat nahi, hum table le lenge"),
    ],
    "smp-chat-011": [  # Old Acme pilot (hidden)
        ("John Miller", "Pilot feedback attached."),
        (ME, "Thanks John, will go through it."),
    ],
    "smp-chat-012": [  # Acme weekly sync meeting chat
        ("Lisa Chen", "Sharing the agenda link."),
        (ME, "Thanks Lisa. Adding the cutover runbook as item 3."),
    ],
    "smp-chat-013": [  # Monsoon pricing (confidential)
        ("David Brooks", "What margin can we hold on Monsoon?"),
        (ME, "32% with the fixed-fee pilot, 36% if we go T&M from month 4."),
        ("Meera Iyer", "Let's go with the pilot."),
    ],
}

# Meeting agendas (calendar body) by event subject. Transcripts arrive with meeting memory (M6).
AGENDAS: dict[str, str] = {
    "Acme weekly sync": "1. Status and risks\n2. UAT progress\n3. Cutover runbook\n4. AOB",
    "Meera / you 1:1": "Team updates, escalations, hiring.",
    "Falcon steering committee": "Timeline, migration rehearsal results, risks, decisions needed.",
    "Orion Health discovery workshop": "Scope, systems inventory, data handling, next steps.",
    "Kestrel all hands": "Q3 results, Q4 priorities, recognition.",
    "Doctor appointment": "",
    "Operation Monsoon pricing review": "Pricing options, margin scenarios, decision.",
}

# Meeting transcripts (M6), as Teams would attribute them. Keys: a series' most recent past
# occurrence ("acme:latest") and the one before ("acme:previous"), or a single meeting's subject.
# `attributed=False` is a meeting where the organisation turned speaker attribution off.
# "John Miller (Guest)" is how Teams shows a federated attendee. Tom Becker (the vendor, someone you
# know) and Jordan Lee (nobody you know) weren't invited.
TRANSCRIPTS: dict[str, tuple[bool, list[tuple[str, str]]]] = {
    "acme:latest": (
        True,
        [
            (ME, "Thanks everyone. Quick agenda today: status, UAT and the cutover runbook."),
            ("John Miller (Guest)", "Before we start, the go-live has to be on a weekend."),
            ("John Miller (Guest)", "We can't take the store systems down on a weekday."),
            ("Lisa Chen", "Also, we need the rollback to be tested end to end before the cutover."),
            (ME, "Understood. I'll share the updated cutover runbook by Thursday EOD."),
            ("Lisa Chen", "And UAT sign-off needs two business owners, not one."),
            ("Meera Iyer", "Agreed, let's go with a weekend go-live then, on the 8th of November."),
            ("John Miller (Guest)", "What's the plan if the payment gateway certification slips?"),
            (ME, "That's a real risk. We will raise it with CloudNest this week."),
            ("Tom Becker", "From the CloudNest side, the new certificates are ready."),
            ("Jordan Lee", "Sorry, joining late from the store operations team."),
            ("Lisa Chen", "Rahul, can you send the UAT defect list to me by tomorrow?"),
            (ME, "One idea: what if we run a dress rehearsal on the Saturday before?"),
            ("John Miller (Guest)", "Good idea. Decision then: dress rehearsal on the 1st of November."),
        ],
    ),
    "acme:previous": (
        True,
        [
            ("Lisa Chen", "The new reports must load in under three seconds for store managers."),
            ("John Miller (Guest)", "For the contract annex, the signatory's PAN is ABCPE1234F."),
            (ME, "I'll check the performance numbers and get back to you by Monday."),
            ("Meera Iyer", "We decided to keep the old reporting server until December."),
            ("Lisa Chen", "My concern is that the data migration window looks tight."),
        ],
    ),
    "1on1:latest": (
        True,
        [
            ("Meera Iyer", "How is the Bluefin hiring going?"),
            (ME, "Two candidates are in the final round. I'll send you the shortlist tomorrow morning."),
            ("Meera Iyer", "Good. Also, please prepare the Q4 resource plan before Thursday."),
            ("Meera Iyer", "We agreed that Ana takes over the Orion workstream from next month."),
            (ME, "Sure, will do."),
        ],
    ),
    "Orion Health discovery workshop": (
        True,
        [
            (ME, "Thanks for making time, Emily. Let's start with scope."),
            ("Emily Park", "All patient data has to stay in India, that's a hard requirement for us."),
            ("Emily Park", "We also need audit logs for every access to health records."),
            ("Priya Nair", "Our systems inventory so far is about 40 applications."),
            ("Emily Park", "Is there an option to start with the claims system first?"),
            (ME, "Maybe we could pilot with claims and then expand to the rest."),
            (ME, "We'll share the discovery report by next Friday."),
        ],
    ),
    "Kestrel all hands": (
        False,
        [
            ("David Brooks", "Welcome everyone to the all hands."),
            ("David Brooks", "Q3 revenue grew 14 percent, thanks to all of you."),
            ("David Brooks", "For Q4, our priority is client retention and delivery quality."),
            ("David Brooks", "We decided to open a new delivery centre in Pune next year."),
            ("David Brooks", "Please complete the security training by the end of the month."),
        ],
    ),
}
