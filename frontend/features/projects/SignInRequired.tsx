import styles from "./projects.module.css";

/**
 * Shown by C's SessionGate on 401. The login entry point comes from deployment config; when it is
 * missing we say so instead of rendering a button that does nothing. No local password flow.
 */
export function SignInRequired({ login_url, expired = false }: { login_url: string | null; expired?: boolean }) {
  return (
    <main className={styles.signIn}>
      <h1>{expired ? "Your session has ended" : "Sign in to Stellaris"}</h1>
      <p className="prose">
        {expired
          ? "Sign in again to continue. Text you had not sent may need to be re-entered."
          : "Your research projects, files and results are private to your account."}
      </p>
      {login_url ? (
        <a href={login_url} className={styles.signInLink}>Sign in</a>
      ) : (
        <p className={styles.configNote} role="alert">
          Sign-in is not configured for this deployment. Ask the administrator to set the login entry point.
        </p>
      )}
    </main>
  );
}
