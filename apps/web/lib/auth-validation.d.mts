export function isValidEmail(value: string): boolean;

export type BackendIdentityResponse = {
  user: { id: string; email?: string; email_confirmed_at?: string | null };
  profile: { id: string; account_status: string; [key: string]: unknown };
};

export type BackendSessionValidationResult<TIdentity = BackendIdentityResponse> =
  | { status: "valid"; identity: TIdentity }
  | { status: "rejected" }
  | { status: "unavailable" };

export function verifyBackendSession<TIdentity = BackendIdentityResponse>(
  apiBase: string,
  session: { access_token: string; user: { id: string } },
  fetchImpl?: typeof fetch,
): Promise<BackendSessionValidationResult<TIdentity>>;
