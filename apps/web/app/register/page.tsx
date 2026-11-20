import AuthOnboardingRoute from "@/components/reference-ui/AuthOnboardingRoute";

/** Register route intentionally reuses the canonical auth flow used by /login. */
export default function RegisterPage() {
  return <AuthOnboardingRoute />;
}
