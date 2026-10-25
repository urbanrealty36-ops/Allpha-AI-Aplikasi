import { redirect } from "next/navigation";

/** The canonical signed-in entry is the reference Feed, not a profile/settings landing page. */
export default function HomePage() {
  redirect("/feed");
}
