import { useEffect, useState } from "react";
import {
  KeyRound,
  Monitor,
  RefreshCw,
  ShieldCheck,
  Smartphone,
} from "lucide-react";
import { api, download, message } from "./api";
import { useShop } from "./context";

const actions = {
  setup: "Set up two-factor authentication",
  disable: "Disable two-factor authentication",
  recovery: "Generate new recovery codes",
  password: "Change password",
};
const eventLabels = {
  account_created: "Account created",
  login: "Sign-in",
  logout: "Signed out",
  verification: "Security verification",
  "2fa_setup": "Authenticator setup started",
  "2fa_enabled": "Two-factor authentication enabled",
  "2fa_disabled": "Two-factor authentication disabled",
  recovery_codes_changed: "Recovery codes regenerated",
  password_changed: "Password changed",
  other_sessions_revoked: "Other devices signed out",
  session_revoked: "Device signed out",
};

function when(value) {
  return value
    ? new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value))
    : "Not recorded";
}
function device(agent = "") {
  const browser = /Edg\//.test(agent)
    ? "Edge"
    : /Firefox\//.test(agent)
      ? "Firefox"
      : /Chrome\//.test(agent)
        ? "Chrome"
        : /Safari\//.test(agent)
          ? "Safari"
          : "Browser";
  const platform = /iPhone|iPad/.test(agent)
    ? "iOS"
    : /Android/.test(agent)
      ? "Android"
      : /Windows/.test(agent)
        ? "Windows"
        : /Macintosh/.test(agent)
          ? "macOS"
          : /Linux/.test(agent)
            ? "Linux"
            : "Unknown device";
  return `${browser} · ${platform}`;
}

export default function AccountSecurity() {
  const { user, accept, notify } = useShop();
  const [security, setSecurity] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [action, setAction] = useState("");
  const [proof, setProof] = useState({
    password: "",
    otp_code: "",
    new_password: "",
    confirmation: "",
  });
  const [setup, setSetup] = useState(null);
  const [qr, setQr] = useState("");
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState([]);
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  async function refresh() {
    const response = await api.get("/auth/security");
    setSecurity(response.data);
  }
  useEffect(() => {
    let active = true;
    api
      .get("/auth/security")
      .then((r) => {
        if (active) setSecurity(r.data);
      })
      .catch((e) => {
        if (active) setError(message(e));
      });
    return () => {
      active = false;
    };
  }, [user.id]);

  function resetForm() {
    setAction("");
    setProof({
      password: "",
      otp_code: "",
      new_password: "",
      confirmation: "",
    });
    setSetup(null);
    setQr("");
    setCode("");
  }
  async function submit(e) {
    e.preventDefault();
    if (busy) return;
    if (action === "password" && proof.new_password !== proof.confirmation) {
      setError("The new passwords do not match.");
      return;
    }
    setError("");
    setBusy(true);
    try {
      if (action === "setup") {
        const result = (
          await api.post("/auth/2fa/setup", { password: proof.password })
        ).data;
        setSetup(result);
        setProof((p) => ({ ...p, password: "" }));
        try {
          const { default: QRCode } = await import("qrcode");
          setQr(await QRCode.toDataURL(result.uri, { width: 220, margin: 2 }));
        } catch {
          setError(
            "The QR code could not load. Add the setup key manually in your authenticator app.",
          );
        }
      } else {
        const result =
          action === "password"
            ? await api.put("/auth/password", {
                password: proof.password,
                otp_code: proof.otp_code,
                new_password: proof.new_password,
              })
            : await api.post(
                `/auth/2fa/${action === "recovery" ? "recovery-codes" : "disable"}`,
                { password: proof.password, otp_code: proof.otp_code },
              );
        await accept(result.data);
        setCodes(result.data.recovery_codes || []);
        resetForm();
        await refresh();
        notify(
          action === "password"
            ? "Password changed. Other devices have been signed out."
            : action === "disable"
              ? "Two-factor authentication disabled."
              : "New recovery codes created. The previous codes no longer work.",
        );
      }
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  async function confirm(e) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const result = (await api.post("/auth/2fa/confirm", { otp_code: code }))
        .data;
      await accept(result);
      setCodes(result.recovery_codes);
      resetForm();
      await refresh();
      notify("Two-factor authentication enabled. Save your recovery codes.");
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  async function revoke(id) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await api.delete(`/auth/sessions/${id}`);
      await refresh();
      notify(
        id === "others" ? "Other devices signed out." : "Device signed out.",
      );
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  function start(value) {
    resetForm();
    setError("");
    setAction(value);
  }

  return (
    <div className="account-security">
      <div className="security-heading">
        <div>
          <p className="eyebrow">YOUR ACCOUNT, PROTECTED</p>
          <h2>Security & sign-in.</h2>
        </div>
        <ShieldCheck size={30} />
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {!security ? (
        <button
          className="outline"
          disabled={busy}
          onClick={() =>
            refresh()
              .then(() => setError(""))
              .catch((e) => setError(message(e)))
          }
        >
          Load security details
        </button>
      ) : (
        <>
          <div className="security-grid">
            <section className="security-card">
              <div className="security-card-title">
                <Smartphone size={22} />
                <h3>Two-factor authentication</h3>
              </div>
              <span
                className={`security-status ${security.two_factor_enabled ? "enabled" : ""}`}
              >
                {security.two_factor_enabled ? "Enabled" : "Not enabled"}
              </span>
              <p>
                Protect your account with a code from your authenticator app.
              </p>
              {security.two_factor_enabled && (
                <p className="metadata">
                  {security.recovery_codes_remaining} recovery codes remaining.
                </p>
              )}
              <div className="button-row">
                {!security.two_factor_enabled ? (
                  <button disabled={busy} onClick={() => start("setup")}>
                    Enable two-factor authentication
                  </button>
                ) : (
                  <>
                    <button
                      className="outline"
                      disabled={busy}
                      onClick={() => start("recovery")}
                    >
                      New recovery codes
                    </button>
                    <button
                      className="why"
                      disabled={busy}
                      onClick={() => start("disable")}
                    >
                      Disable 2FA
                    </button>
                  </>
                )}
              </div>
            </section>
            <section className="security-card">
              <div className="security-card-title">
                <KeyRound size={22} />
                <h3>Password</h3>
              </div>
              <p>Choose a unique password with at least 10 characters.</p>
              <p className="metadata">
                Changing your password signs out other devices.
              </p>
              <button
                className="outline"
                disabled={busy}
                onClick={() => start("password")}
              >
                Change password
              </button>
            </section>
          </div>

          {action && !setup && (
            <form className="security-card security-form" onSubmit={submit}>
              <h3>{actions[action]}</h3>
              <label>
                Current password
                <input
                  required
                  autoFocus
                  type="password"
                  autoComplete="current-password"
                  maxLength={128}
                  value={proof.password}
                  onChange={(e) =>
                    setProof((p) => ({ ...p, password: e.target.value }))
                  }
                />
              </label>
              {security.two_factor_enabled && (
                <label>
                  Authenticator or recovery code
                  <input
                    required
                    autoComplete="one-time-code"
                    maxLength={40}
                    value={proof.otp_code}
                    onChange={(e) =>
                      setProof((p) => ({ ...p, otp_code: e.target.value }))
                    }
                  />
                  <small>
                    Use a fresh code. Each authenticator code can be used once.
                  </small>
                </label>
              )}
              {action === "password" && (
                <>
                  <label>
                    New password
                    <input
                      required
                      type="password"
                      autoComplete="new-password"
                      minLength={10}
                      maxLength={128}
                      value={proof.new_password}
                      onChange={(e) =>
                        setProof((p) => ({
                          ...p,
                          new_password: e.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Confirm new password
                    <input
                      required
                      type="password"
                      autoComplete="new-password"
                      minLength={10}
                      maxLength={128}
                      value={proof.confirmation}
                      onChange={(e) =>
                        setProof((p) => ({
                          ...p,
                          confirmation: e.target.value,
                        }))
                      }
                    />
                  </label>
                </>
              )}
              <p className="metadata">
                Completing this change signs out other devices.
              </p>
              <div className="button-row">
                <button disabled={busy}>
                  {busy
                    ? "Verifying…"
                    : action === "setup"
                      ? "Continue to authenticator setup"
                      : actions[action]}
                </button>
                <button
                  type="button"
                  className="outline"
                  disabled={busy}
                  onClick={resetForm}
                >
                  Cancel
                </button>
              </div>
            </form>
          )}

          {setup && (
            <form className="security-card security-form" onSubmit={confirm}>
              <h3>Connect your authenticator app</h3>
              <p>
                Scan this QR code with Google Authenticator, Microsoft
                Authenticator, 1Password, or another compatible app.
              </p>
              {qr && (
                <img
                  className="authenticator-qr"
                  src={qr}
                  alt="Scan to add your SCENTHAUS account to your authenticator app"
                />
              )}
              <label>
                Manual setup key
                <code className="setup-key">{setup.secret}</code>
              </label>
              <p className="metadata">
                Setup expires after 10 minutes. Two-factor authentication stays
                off until you verify.
              </p>
              <label>
                Six-digit authenticator code
                <input
                  required
                  autoFocus
                  autoComplete="one-time-code"
                  inputMode="numeric"
                  pattern="[0-9]{6}"
                  minLength={6}
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
              </label>
              <div className="button-row">
                <button disabled={busy}>
                  {busy ? "Verifying…" : "Verify & enable 2FA"}
                </button>
                <button
                  type="button"
                  className="outline"
                  disabled={busy}
                  onClick={resetForm}
                >
                  Cancel
                </button>
              </div>
            </form>
          )}

          {codes.length > 0 && (
            <section
              className="security-card recovery-panel"
              aria-label="Your recovery codes"
            >
              <h3>Save your recovery codes</h3>
              <p>
                Each code signs you in once if you lose access to your
                authenticator. Keep these in a safe place; they will not be
                shown again.
              </p>
              <div className="recovery-codes">
                {codes.map((entry) => (
                  <code key={entry}>{entry}</code>
                ))}
              </div>
              <div className="button-row">
                <button
                  className="outline"
                  onClick={() =>
                    download(
                      `SCENTHAUS recovery codes\n${user.email}\n\n${codes.join("\n")}\n\nEach code can be used once. Keep this file private.`,
                      "scenthaus-recovery-codes.txt",
                      "text/plain",
                    )
                  }
                >
                  Download codes
                </button>
                <button onClick={() => setCodes([])}>
                  I have saved my codes
                </button>
              </div>
            </section>
          )}

          <section className="security-card">
            <div className="security-card-title">
              <Monitor size={22} />
              <h3>Active sessions</h3>
            </div>
            <p>Devices signed into your account. Times use {timezone}.</p>
            <p className="metadata">
              Location is approximate and may reflect a VPN. Sessions last up to
              seven days; activity updates about every five minutes.
            </p>
            <div className="session-list">
              {security.sessions.map((session) => (
                <article className="session-item" key={session.id}>
                  <div>
                    <strong>{device(session.user_agent || "")}</strong>
                    {session.current && (
                      <span className="security-status enabled">
                        This device
                      </span>
                    )}
                    <p>
                      {session.location || "Location unavailable"} ·{" "}
                      {session.ip_address || "IP unavailable"}
                    </p>
                    <p className="metadata">
                      Signed in: {when(session.login_at)}
                      <br />
                      Last active: {when(session.last_active_at)}
                      <br />
                      Expires: {when(session.expires_at)}
                    </p>
                  </div>
                  {!session.current && (
                    <button
                      className="outline"
                      disabled={busy}
                      onClick={() => revoke(session.id)}
                    >
                      Sign out device
                    </button>
                  )}
                </article>
              ))}
            </div>
            <div className="button-row">
              <button
                className="outline"
                disabled={busy || security.sessions.length <= 1}
                onClick={() => revoke("others")}
              >
                Sign out all other devices
              </button>
              <button
                className="why"
                disabled={busy}
                onClick={() => refresh().catch((e) => setError(message(e)))}
              >
                <RefreshCw size={14} /> Refresh sessions
              </button>
            </div>
          </section>

          <section className="security-card">
            <h3>Recent login & security activity</h3>
            <p className="metadata">
              Your 30 most recent events. Security history is retained for 90
              days.
            </p>
            {security.history.length ? (
              <ol className="security-history">
                {security.history.map((event) => (
                  <li key={event.id}>
                    <div>
                      <strong>
                        {eventLabels[event.kind] || "Security activity"}
                        {!event.success && " · Failed"}
                      </strong>
                      <p className="metadata">
                        {event.location || "Location unavailable"} ·{" "}
                        {event.ip_address || "IP unavailable"} ·{" "}
                        {device(event.user_agent || "")}
                      </p>
                    </div>
                    <time dateTime={event.created_at}>
                      {when(event.created_at)}
                    </time>
                  </li>
                ))}
              </ol>
            ) : (
              <p>No recent activity recorded.</p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
