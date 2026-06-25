import { useEffect, useState } from "react";
import {
  clearAuthSession,
  fetchCurrentUser,
  readAuthSession,
  type AuthTokenResponse,
  type AuthUser,
} from "../api/kslClient";
import { AuthPage } from "../features/auth/AuthPage";
import { LearningWorkspace } from "../features/workspace/LearningWorkspace";

type AuthState =
  | { status: "loading" }
  | { status: "signed-out" }
  | { status: "signed-in"; user: AuthUser };

export function App() {
  const [authState, setAuthState] = useState<AuthState>({ status: "loading" });

  useEffect(() => {
    const existingSession = readAuthSession();
    if (!existingSession) {
      setAuthState({ status: "signed-out" });
      return;
    }

    let cancelled = false;

    void fetchCurrentUser()
      .then((user) => {
        if (!cancelled) {
          setAuthState({ status: "signed-in", user });
        }
      })
      .catch(() => {
        clearAuthSession();
        if (!cancelled) {
          setAuthState({ status: "signed-out" });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  function handleAuthenticated(payload: AuthTokenResponse) {
    setAuthState({ status: "signed-in", user: payload.user });
  }

  function handleLogout() {
    clearAuthSession();
    setAuthState({ status: "signed-out" });
  }

  if (authState.status === "loading") {
    return (
      <main className="auth-shell auth-shell-loading">
        <section className="auth-card auth-card-loading">
          <p className="voice-kicker">Loading session</p>
          <h2>Checking your access...</h2>
        </section>
      </main>
    );
  }

  if (authState.status === "signed-out") {
    return <AuthPage onAuthenticated={handleAuthenticated} />;
  }

  return (
    <LearningWorkspace user={authState.user} onLogout={handleLogout} />
  );
}
