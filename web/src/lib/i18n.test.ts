import {describe, expect, it} from "vitest";
import {copy, isLocale} from "./i18n";

describe("bilingual interface", () => {
  it("accepts only supported locale route segments", () => {
    expect(isLocale("es")).toBe(true);
    expect(isLocale("en")).toBe(true);
    expect(isLocale("fr")).toBe(false);
  });
  it("keeps the access and profile copy complete in both languages", () => {
    for (const locale of ["es", "en"] as const) {
      expect(copy[locale].access).toBeTruthy();
      expect(copy[locale].profile).toBeTruthy();
      expect(copy[locale].language).toBeTruthy();
    }
  });
});
