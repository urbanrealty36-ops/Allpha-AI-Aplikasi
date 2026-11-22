/** Validate a user-entered email before submitting Supabase Auth credentials. */
export function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

/**
 * Resolve a browser session through the canonical FastAPI identity boundary.
 * FastAPI verifies Supabase Auth, auth.sessions revocation and account status.
 * Only explicit rejection clears a local session; transient failures preserve it.
 */
export async function verifyBackendSession(apiBase, session, fetchImpl = fetch) {
  try {
    const response = await fetchImpl(`${apiBase.replace(/\/$/, "")}/v1/me`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${session.access_token}`,
        Accept: "application/json",
      },
      cache: "no-store",
    });

    if (response.status === 401 || response.status === 403) {
      return { status: "rejected" };
    }
    if (!response.ok) {
      return { status: "unavailable" };
    }

    const identity = await response.json();
    if (!identity?.user?.id || !identity.profile) {
      return { status: "unavailable" };
    }
    if (identity.user.id !== session.user.id || identity.profile.id !== session.user.id) {
      return { status: "rejected" };
    }
    if (identity.profile.account_status !== "active") {
      return { status: "rejected" };
    }
    return { status: "valid", identity };
  } catch {
    return { status: "unavailable" };
  }
}
