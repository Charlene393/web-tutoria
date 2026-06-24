import { useState } from "react";
import type { FormEvent } from "react";
import {
  loginAuth,
  persistAuthSession,
  registerAuth,
  type AuthTokenResponse,
} from "../../api/kslClient";

type AuthMode = "login" | "register";

export function AuthPage({
  onAuthenticated,
}: {
  onAuthenticated: (payload: AuthTokenResponse) => void;
}) {
  const [mode, setMode] = useState<AuthMode>("login");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const isRegisterMode = mode === "register";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage(null);

    if (isRegisterMode && password !== confirmPassword) {
      setErrorMessage("Passwords do not match yet.");
      return;
    }

    setIsSubmitting(true);

    try {
      const payload = isRegisterMode
        ? await registerAuth({
            full_name: fullName.trim() || null,
            email: email.trim(),
            password,
          })
        : await loginAuth({
            email: email.trim(),
            password,
          });

      persistAuthSession(payload);
      onAuthenticated(payload);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Authentication failed.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="">
        <h1 className="auth-hero-title">Tutoria</h1>
      </section>

      <section className="auth-card">
        <div className="auth-switcher" role="tablist" aria-label="Authentication mode">
          <button
            type="button"
            className={mode === "login" ? "is-active" : ""}
            onClick={() => setMode("login")}
          >
            Sign in
          </button>
          <button
            type="button"
            className={mode === "register" ? "is-active" : ""}
            onClick={() => setMode("register")}
          >
            Create account
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <header>
            <p className="voice-kicker">{isRegisterMode ? "Create account" : "Welcome back"}</p>
          </header>

          {isRegisterMode ? (
            <label>
              <span>Full name</span>
              <input
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                placeholder="Charlene Mbugua"
                autoComplete="name"
              />
            </label>
          ) : null}

          <label>
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="student@example.com"
              autoComplete="email"
              required
            />
          </label>

          <label>
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="At least 8 characters"
              autoComplete={isRegisterMode ? "new-password" : "current-password"}
              required
            />
          </label>

          {isRegisterMode ? (
            <label>
              <span>Confirm password</span>
              <input
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                placeholder="Repeat your password"
                autoComplete="new-password"
                required
              />
            </label>
          ) : null}

          {errorMessage ? <p className="auth-error">{errorMessage}</p> : null}

          <button className="auth-submit" type="submit" disabled={isSubmitting}>
            {isSubmitting
              ? "Please wait..."
              : isRegisterMode
                ? "Create account"
                : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
