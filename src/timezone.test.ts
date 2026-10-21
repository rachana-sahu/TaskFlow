import { describe, expect, it } from "vitest";
import { resolveRegistrationTimezone } from "./timezone";

describe("registration timezone resolution", () => {
  it("preserves a valid browser timezone", () => {
    expect(resolveRegistrationTimezone("America/Los_Angeles")).toBe("America/Los_Angeles");
  });

  it("uses the default when the browser timezone is missing or unsupported", () => {
    expect(resolveRegistrationTimezone(undefined)).toBe("Asia/Kolkata");
    expect(resolveRegistrationTimezone("Etc/Unknown")).toBe("Asia/Kolkata");
  });
});
