/** Validate a user-entered email before submitting Supabase Auth credentials. */
export function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

/**
 * Validate a browser session against the canonical FastAPI identity boundary.
 * Supabase Auth alone cannot detect an application-level session revocation.
 * Only an explicit 401/403 or a mismatched/inactive identity is definitive;
 * transport, server, and malformed-contract failures preserve the local session.
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
    return { status: "valid" };
  } catch {
    return { status: "unavailable" };
  }
}
