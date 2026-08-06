import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it} from "vitest";
import type {Competition} from "./api";
import {RulesSnapshotConfirmation} from "../components/rules-snapshot-confirmation";

const competition = {
  id: "c1", league_id: "l1", name: "Otoño",
  starts_at: "2026-09-01T00:00:00Z", ends_at: "2026-09-30T23:59:59Z",
  status: "active", started_at: "2026-08-06T12:00:00Z",
  rules_snapshot: {
    version: "1",
    calendar: {
      market: "XNYS", timezone: "America/New_York",
      starts_at: "2026-09-01T00:00:00Z", ends_at: "2026-09-30T23:59:59Z"
    },
    rules: {currency: "USD", initial_capital: "3000.00"}
  }
} satisfies Competition;

describe("competition rules snapshot", () => {
  it.each([
    ["es", "Calendario y reglas copiados de forma inmutable"],
    ["en", "Calendar and rules copied immutably"]
  ] as const)("shows the immutable confirmation in %s", (locale, message) => {
    const html = renderToStaticMarkup(
      <RulesSnapshotConfirmation locale={locale} competition={competition}/>
    );
    expect(html).toContain(message);
    expect(html).toContain("3000.00");
    expect(html).toContain("America/New_York");
  });
});
