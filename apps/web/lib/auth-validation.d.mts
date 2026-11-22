export function isValidEmail(value: string): boolean;

export type BackendSessionValidationResult =
  | { status: "valid" }
  | { status: "rejected" }
  | { status: "unavailable" };

export function verifyBackendSession(
  apiBase: string,
  session: { access_token: string; user: { id: string } },
  fetchImpl?: typeof fetch,
): Promise<BackendSessionValidationResult>;
