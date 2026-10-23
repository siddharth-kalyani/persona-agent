/** Home: what needs you, how far Vanimo is set up, and the facts it works from. Task-first, no
 * greeting hero: a status strip, a setup checklist until it's done, promises coming due, and your
 * profile as Vanimo reads it. */
import { Avatar, Button, Link, makeStyles, MessageBar, MessageBarBody, tokens } from "@fluentui/react-components";
import {
  ArrowRight16Regular,
  CheckmarkCircle20Filled,
  Circle20Regular,
  Mail16Regular,
  TaskListSquareLtr16Regular,
} from "@fluentui/react-icons";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, type DraftingStatus, type DraftSummary, type LearningStatus, type Ledger, type Me } from "../api/client";
import { useApi } from "../api/context";
import {
  EmptyState,
  List,
  ListRow,
  Page,
  PageSkeleton,
  Pill,
  Section,
  Stat,
  StatStrip,
  Surface,
  Time,
  typo,
  vt,
} from "../ui";

const useStyles = makeStyles({
  columns: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) 320px",
    gap: "32px",
    alignItems: "start",
    "@media (max-width: 899px)": { gridTemplateColumns: "minmax(0, 1fr)" },
  },
  main: { display: "grid", gap: "32px", minWidth: 0 },
  side: { display: "grid", gap: "16px", minWidth: 0 },
  person: { display: "grid", gridTemplateColumns: "auto minmax(0, 1fr)", gap: "12px", alignItems: "center" },
  personText: { display: "grid", minWidth: 0 },
  personLabel: { ...typo.label, color: vt.text3 },
  personName: { ...typo.itemTitle, color: vt.text1 },
  personMeta: { ...typo.meta, color: vt.text2 },
  divider: { height: "1px", backgroundColor: tokens.colorNeutralStroke3, margin: "16px 0" },
  roles: { display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "12px" },
  fact: { ...typo.meta, color: vt.text2, margin: 0 },
  steps: { display: "grid", gap: 0 },
  stepIconDone: { color: vt.success },
  stepIconTodo: { color: vt.text3 },
  progress: { ...typo.meta, color: vt.text2, ...typo.tabular },
});

export function errorText(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.code === "consent_required") return "Vanimo needs admin consent for its Microsoft 365 permissions.";
    if (err.code === "not_assigned") return "Your account hasn't been given access to Vanimo yet. Ask your IT admin.";
    if (err.code === "db_unavailable") return "Vanimo is waking up. Try again in a few seconds.";
    if (err.code === "unauthorized_client") return "This app isn't allowed to call Vanimo.";
    if (err.code === "graph_error") return `Microsoft 365 returned an error (${String(err.body.graphCode ?? err.status)}).`;
    if (err.code === "pipeline_paused")
      return "Vanimo is paused for your organisation while an admin checks a sensitive-data finding. Nothing new is read or drafted until then.";
    if (err.code === "redaction_unavailable")
      return "Vanimo's sensitive-data check is unreachable right now, so nothing was read. Try again in a minute.";
    if (err.code === "model_check_unavailable")
      return "Vanimo's AI safety check is unreachable right now, so no AI was used. Try again in a minute.";
    if (err.code === "model_check_blocked")
      return "Vanimo's safety check found personal details that should have been hidden, so it stopped. Your admin has been told.";
    return `Something went wrong (${err.code}).`;
  }
  return "Something went wrong. Try again.";
}

const ROLE_LABELS: Record<string, string> = {
  "Vanimo.User": "User",
  "Vanimo.Admin": "Admin",
  "Vanimo.SuperAdmin": "Super-admin",
};

/** Optional extras for the strip and checklist: each loads on its own and never blocks the page. */
function useExtras() {
  const api = useApi();
  const [learning, setLearning] = useState<LearningStatus | null>(null);
  const [drafting, setDrafting] = useState<DraftingStatus | null>(null);
  const [drafts, setDrafts] = useState<DraftSummary[] | null>(null);
  const [ledger, setLedger] = useState<Ledger | null>(null);
  useEffect(() => {
    let live = true;
    const keep = <T,>(set: (v: T) => void) => (v: T) => live && set(v);
    api.learning().then(keep(setLearning), () => undefined);
    api.draftingStatus().then(keep(setDrafting), () => undefined);
    api.drafts().then(keep(setDrafts), () => undefined);
    api.commitments("open").then(keep(setLedger), () => undefined);
    return () => {
      live = false;
    };
  }, [api]);
  return { learning, drafting, drafts, ledger };
}

export function Home() {
  const styles = useStyles();
  const api = useApi();
  const navigate = useNavigate();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { learning, drafting, drafts, ledger } = useExtras();

  useEffect(() => {
    let live = true;
    api.me().then(
      (m) => live && setMe(m),
      (e) => live && setError(errorText(e)),
    );
    return () => {
      live = false;
    };
  }, [api]);

  if (error)
    return (
      <Page title="Home">
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      </Page>
    );
  if (!me) return <PageSkeleton label="Loading your profile…" />;

  const reviewDone = me.onboardingState !== "review_pending";
  const learned = (learning?.stored.total ?? 0) > 0;
  const drafted = (drafts?.length ?? 0) > 0;
  const steps = [
    { done: reviewDone, label: "Choose what Vanimo learns from", detail: "Nothing is read beyond headers until you finish or skip this.", path: "/setup" },
    { done: learned, label: "Learn how you write", detail: "From your own sent mail and chats, redacted before it's stored.", path: "/learning" },
    { done: drafted, label: "Draft your first reply", detail: "Pick a conversation; Vanimo never sends anything.", path: "/draft" },
  ]; // prettier-ignore
  const doneCount = steps.filter((s) => s.done).length;
  const weekAgo = Date.now() - 7 * 86_400_000;
  const draftsThisWeek = drafts?.filter((d) => new Date(d.createdAt).getTime() > weekAgo).length;
  const due = (ledger?.items ?? [])
    .filter((c) => c.dueAt)
    .sort((a, b) => new Date(a.dueAt!).getTime() - new Date(b.dueAt!).getTime())
    .slice(0, 4);
  const roles = me.roles.map((r) => ROLE_LABELS[r] ?? r);
  const today = new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });

  return (
    <Page
      title="Home"
      eyebrow={
        <>
          <span>{today}</span>
          <Pill>{me.dataSource === "sample" ? "Sample workspace" : "Microsoft 365"}</Pill>
        </>
      }
      actions={
        <Button appearance="primary" onClick={() => navigate("/draft")}>
          Draft a reply
        </Button>
      }
    >
      {me.dataSource === "sample" && (
        <MessageBar intent="info">
          <MessageBarBody>
            You're seeing the sample workspace — a fictional company, Kestrel Analytics. Your own Microsoft 365 data
            appears when you sign in with Microsoft.
          </MessageBarBody>
        </MessageBar>
      )}

      <StatStrip label="At a glance">
        <Stat
          value={ledger ? ledger.open : "–"}
          label="Open commitments"
          hint={ledger ? (ledger.overdue ? `${ledger.overdue} overdue` : `${ledger.dueSoon} due soon`) : undefined}
          onClick={() => navigate("/commitments")}
        />
        <Stat
          value={learning ? learning.stored.total : "–"}
          label="Messages learned"
          hint={learning ? `${learning.styleCards} style cards` : undefined}
          onClick={() => navigate("/learning")}
        />
        <Stat
          value={draftsThisWeek ?? "–"}
          label="Drafts this week"
          hint={drafting ? (drafting.generator === "offline" ? "Offline stand-in" : "Claude on Amazon Bedrock") : undefined}
          onClick={() => navigate("/draft")}
        />
      </StatStrip>

      <div className={styles.columns}>
        <div className={styles.main}>
          {doneCount < steps.length && (
            <Section
              title="Get set up"
              description="Three steps, in order. You can change your choices any time."
              actions={<span className={styles.progress}>{doneCount} of {steps.length} done</span>}
            >
              <List bordered label="Setup steps">
                {steps.map((s) => (
                  <ListRow
                    key={s.path}
                    leading={
                      s.done ? (
                        <CheckmarkCircle20Filled className={styles.stepIconDone} aria-label="Done" />
                      ) : (
                        <Circle20Regular className={styles.stepIconTodo} aria-label="To do" />
                      )
                    }
                    title={
                      s.done ? (
                        s.label
                      ) : (
                        <Link
                          href={s.path}
                          onClick={(e) => {
                            e.preventDefault();
                            navigate(s.path);
                          }}
                        >
                          {s.label}
                        </Link>
                      )
                    }
                    meta={s.detail}
                    wrap
                    trailing={s.done ? <Pill tone="success">Done</Pill> : <ArrowRight16Regular aria-hidden />}
                  />
                ))}
              </List>
            </Section>
          )}

          <Section
            title="Coming due"
            description="Promises you made in email, chats and meetings."
            actions={
              <Button appearance="subtle" size="small" onClick={() => navigate("/commitments")}>
                All commitments
              </Button>
            }
          >
            {due.length > 0 ? (
              <List bordered label="Commitments coming due">
                {due.map((c) => (
                  <ListRow
                    key={c.id}
                    leading={<TaskListSquareLtr16Regular aria-hidden />}
                    title={c.what}
                    meta={`To ${c.relationship}${c.duePhrase ? ` · “${c.duePhrase}”` : ""}`}
                    trailing={
                      new Date(c.dueAt!).getTime() < Date.now() ? (
                        <Pill tone="danger">Overdue</Pill>
                      ) : (
                        <Time iso={c.dueAt!} />
                      )
                    }
                    onClick={() => navigate("/commitments")}
                  />
                ))}
              </List>
            ) : (
              <EmptyState icon={<TaskListSquareLtr16Regular />} title="Nothing due">
                When you promise something with a date (“I'll send it by Friday”), it shows up here.
              </EmptyState>
            )}
          </Section>

          <Section title="Your last 5 sent emails" description="Subjects only, read live. Vanimo doesn't store them.">
            <List bordered label="Last sent emails">
              {me.recentSent.map((m, i) => (
                <ListRow
                  key={i}
                  leading={<Mail16Regular aria-hidden />}
                  title={m.subject || "(no subject)"}
                  meta={`${m.recipientCount} recipient${m.recipientCount === 1 ? "" : "s"}`}
                  trailing={m.sentDateTime ? <Time iso={m.sentDateTime} /> : "—"}
                />
              ))}
              {me.recentSent.length === 0 && <ListRow title="No sent emails found." />}
            </List>
          </Section>
        </div>

        <aside className={styles.side} aria-label="Your profile">
          <Surface padding="m">
            <div className={styles.person}>
              <Avatar name={me.user.displayName ?? undefined} size={36} color="neutral" />
              <div className={styles.personText}>
                <span className={styles.personLabel}>You</span>
                <span className={styles.personName}>{me.user.displayName ?? "—"}</span>
                <span className={styles.personMeta}>
                  {[me.user.jobTitle, me.user.department].filter(Boolean).join(" · ") || "No job title"}
                </span>
              </div>
            </div>
            <div className={styles.divider} />
            <div className={styles.person}>
              <Avatar name={me.manager?.displayName ?? undefined} size={36} color="neutral" />
              <div className={styles.personText}>
                <span className={styles.personLabel}>Your manager</span>
                {me.manager ? (
                  <>
                    <span className={styles.personName}>{me.manager.displayName ?? "—"}</span>
                    <span className={styles.personMeta}>{me.manager.jobTitle ?? ""}</span>
                  </>
                ) : (
                  <span className={styles.personMeta}>No manager listed in your directory.</span>
                )}
              </div>
            </div>
            <div className={styles.roles} aria-label="Your roles">
              {roles.map((r) => (
                <Pill key={r}>{r}</Pill>
              ))}
            </div>
          </Surface>
          <p className={styles.fact}>
            {me.dataSource === "sample"
              ? "Everything here is synthetic. Vanimo reads it exactly as it would read a real mailbox."
              : "Read live from Microsoft 365 with your permission. Vanimo never sends anything on its own."}
          </p>
        </aside>
      </div>
    </Page>
  );
}
