import {
  Button,
  Divider,
  Field,
  Input,
  makeStyles,
  MessageBar,
  MessageBarBody,
  tokens,
} from "@fluentui/react-components";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { AuthFailure, useAuth } from "../auth/session";
import { Mark } from "../shell/Sidebar";
import { typo, vt } from "../ui";

const useStyles = makeStyles({
  panel: {
    width: "min(400px, 100%)",
    display: "grid",
    gap: "20px",
    padding: "32px",
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusXLarge,
    "@media (max-width: 479px)": { padding: "24px 20px", border: "none", backgroundColor: "transparent" },
  },
  brand: { display: "flex", alignItems: "center", gap: "10px", ...typo.itemTitle, fontSize: "15px", fontWeight: 600, color: vt.text1 },
  heading: { display: "grid", gap: "6px" },
  title: { ...typo.pageTitle, color: vt.text1, margin: 0 },
  lead: { ...typo.body, color: vt.text2, margin: 0 },
  form: { display: "grid", gap: "16px" },
  submit: { marginTop: "4px" },
  footer: { ...typo.meta, color: vt.text3, margin: 0, textAlign: "center" },
});

/** The centred panel the signed-out screens share: the mark, a title, a line of purpose, content. */
export function AuthPanel({
  title,
  lead,
  children,
  footer,
}: {
  title: string;
  lead: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const s = useStyles();
  useEffect(() => {
    document.title = `${title} · Vanimo`;
  }, [title]);
  return (
    <div className={s.panel}>
      <div className={s.brand}>
        <Mark size={24} />
        Vanimo
      </div>
      <div className={s.heading}>
        <h1 className={s.title}>{title}</h1>
        <p className={s.lead}>{lead}</p>
      </div>
      {children}
      {footer && <div className={s.footer}>{footer}</div>}
    </div>
  );
}

export function signInError(code: string): string {
  switch (code) {
    case "invalid_credentials":
      return "That email and password don't match. After 5 wrong attempts the account is locked for 15 minutes.";
    case "too_many_attempts":
      return "Too many attempts from this device. Wait a minute and try again.";
    default:
      return "Sign-in failed. Try again.";
  }
}

export function SignIn() {
  const styles = useStyles();
  const auth = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await auth.signInWithPassword(email, password);
    } catch (err) {
      setError(signInError(err instanceof AuthFailure ? err.code : "error"));
      setPassword("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthPanel
      title="Sign in to Vanimo"
      lead="Your writing voice and work memory, inside Outlook and Teams."
      footer="Vanimo drafts; you send. It never sends anything on your behalf."
    >
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}
      {auth.options.password && (
        <form className={styles.form} onSubmit={(e) => void submit(e)}>
          <Field label="Email" required>
            <Input
              size="large"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(_, d) => setEmail(d.value)}
            />
          </Field>
          <Field label="Password" required>
            <Input
              size="large"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(_, d) => setPassword(d.value)}
            />
          </Field>
          <Button
            className={styles.submit}
            appearance="primary"
            size="large"
            type="submit"
            disabled={busy || !email || !password}
          >
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      )}
      {auth.options.password && auth.options.microsoft && <Divider>or</Divider>}
      {auth.options.microsoft && (
        <Button
          size="large"
          appearance={auth.options.password ? "secondary" : "primary"}
          onClick={() => void auth.signInWithMicrosoft()}
        >
          Sign in with Microsoft
        </Button>
      )}
    </AuthPanel>
  );
}
