import {cookies} from "next/headers";
import {redirect} from "next/navigation";

export default async function Index() {
  const locale = (await cookies()).get("tradearena_locale")?.value === "en" ? "en" : "es";
  redirect(`/${locale}`);
}
