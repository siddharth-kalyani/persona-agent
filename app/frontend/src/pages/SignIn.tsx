import {
  Button,
  Card,
  Divider,
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
  card: { width: "min(420px, 100%)", padding: tokens.spacingHorizontalXXL, display: "grid", gap: tokens.spacingVerticalL },
  form: { display: "grid", gap: tokens.spacingVerticalM },
});

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
    <div className={styles.wrap}>
      <Card className={styles.card}>
        <Title3 as="h2">Sign in to Vanimo</Title3>
        <Text>Your writing voice and work memory, inside Outlook and Teams.</Text>
        {error && (
          <MessageBar intent="error">
            <MessageBarBody>{error}</MessageBarBody>
          </MessageBar>
        )}
        {auth.options.password && (
          <form className={styles.form} onSubmit={(e) => void submit(e)}>
            <Field label="Email" required>
              <Input type="email" autoComplete="username" value={email} onChange={(_, d) => setEmail(d.value)} />
            </Field>
            <Field label="Password" required>
              <Input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(_, d) => setPassword(d.value)}
              />
            </Field>
            <Button appearance="primary" type="submit" disabled={busy || !email || !password}>
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        )}
        {auth.options.password && auth.options.microsoft && <Divider>or</Divider>}
        {auth.options.microsoft && (
          <Button appearance={auth.options.password ? "secondary" : "primary"} onClick={() => void auth.signInWithMicrosoft()}>
            Sign in with Microsoft
          </Button>
        )}
      </Card>
    </div>
  );
}
