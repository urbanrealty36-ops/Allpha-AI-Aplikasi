import { redirect } from "next/navigation";

/** First visit must see the reference onboarding/splash before the public feed. */
export default function HomePage() {
  redirect("/welcome");
}
