import {describe, expect, it} from "vitest";
import {invitationPath} from "./invitations";

describe("invitation links", () => {
  it("stay on the selected locale and encode the opaque identifier", () => {
    expect(invitationPath("es", "invite/one")).toBe("/es/invite/invite%2Fone");
    expect(invitationPath("en", "opaque-id")).toBe("/en/invite/opaque-id");
  });
});
