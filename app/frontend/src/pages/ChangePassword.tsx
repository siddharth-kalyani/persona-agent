import {
  Button,
  Caption1,
  Card,
  Field,
  Input,
  makeStyles,
  MessageBar,
  MessageBarBody,
  Text,
  Title3,
  tokens,
} from "@fluentui/react-components";
import { useState, type FormEvent } from "react";
import { AuthFailure, useAuth } from "../auth/session";

const useStyles = makeStyles({
  wrap: { display: "grid", justifyItems: "center", marginTop: "8vh" },
  card: { width: "min(440px, 100%)", padding: tokens.spacingHorizontalXXL, display: "grid", gap: tokens.spacingVerticalL },
  form: { display: "grid", gap: tokens.spacingVerticalM },
});

export const MIN_PASSWORD_LENGTH = 12;

export function changePasswordError(code: string): string {
  switch (code) {
    case "invalid_credentials":
      return "Your current password isn't right.";
    case "password_too_short":
      return `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
    case "password_too_long":
      return "Use at most 128 characters.";
    case "password_too_common":
      return "That password is too easy to guess. Try a longer phrase.";
    case "password_contains_email":
      return "Don't include your email name in the password.";
    case "password_unchanged":
      return "Choose a password different from the one-time password.";
    case "account_locked":
      return "Too many attempts. The account is locked for 15 minutes.";
    default:
      return "Couldn't change the password. Try again.";
  }
}

/** Shown right after signing in with a one-time password; nothing else is reachable until done. */
export function ChangePassword() {
  const styles = useStyles();
  const auth = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mismatch = confirm.length > 0 && next !== confirm;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (next !== confirm) return;
    setBusy(true);
    setError(null);
    try {
      await auth.changePassword(current, next);
    } catch (err) {
      const code = err instanceof AuthFailure ? err.code : "error";
      if (code === "session_expired") auth.expire();
      setError(changePasswordError(code));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.wrap}>
      <Card className={styles.card}>
        <Title3 as="h2">Set your password</Title3>
        <Text>You signed in with a one-time password. Choose your own to continue.</Text>
        {error && (
          <MessageBar intent="error">
            <MessageBarBody>{error}</MessageBarBody>
          </MessageBar>
        )}
        <form className={styles.form} onSubmit={(e) => void submit(e)}>
          <Field label="One-time password" required>
            <Input type="password" autoComplete="current-password" value={current} onChange={(_, d) => setCurrent(d.value)} />
          </Field>
          <Field label="New password" required hint={`At least ${MIN_PASSWORD_LENGTH} characters. A phrase works well.`}>
            <Input type="password" autoComplete="new-password" value={next} onChange={(_, d) => setNext(d.value)} />
          </Field>
          <Field
            label="Confirm new password"
            required
            validationState={mismatch ? "error" : "none"}
            validationMessage={mismatch ? "The passwords don't match." : undefined}
          >
            <Input type="password" autoComplete="new-password" value={confirm} onChange={(_, d) => setConfirm(d.value)} />
          </Field>
          <Button
            appearance="primary"
            type="submit"
            disabled={busy || !current || next.length < MIN_PASSWORD_LENGTH || next !== confirm}
          >
            {busy ? "Saving…" : "Set password"}
          </Button>
        </form>
        <Caption1>Signed in as {auth.email}</Caption1>
      </Card>
    </div>
  );
}
