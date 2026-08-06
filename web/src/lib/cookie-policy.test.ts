import {describe, expect, it} from "vitest";
import {cookiePolicy} from "./cookie-policy";

describe("cookie policy", () => {
  it("uses non-Secure local cookies for an HTTP development origin", () => {
    expect(cookiePolicy("http://localhost:3000")).toEqual({
      secure: false,
      sessionName: "tradearena_session",
      transactionName: "tradearena_login"
    });
  });

  it("uses Secure __Host cookies for an HTTPS deployment", () => {
    expect(cookiePolicy("https://arena.example")).toEqual({
      secure: true,
      sessionName: "__Host-tradearena_session",
      transactionName: "__Host-tradearena_login"
    });
  });
});
