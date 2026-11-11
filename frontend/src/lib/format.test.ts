import { describe, expect, it } from "vitest";
import { dayKey, dayLabel, initials, mmss, rupees, secondsLeft, time } from "./format";

describe("format", () => {
  it("formats money from paise", () => expect(rupees(50000)).toBe("₹500"));
  it("shows clinic time (IST) for a UTC instant", () => expect(time("2026-10-19T10:54:00Z")).toBe("4:24 pm"));
  it("rolls the date over at IST midnight, not UTC", () => expect(dayKey("2026-10-19T19:00:00Z")).toBe("2026-10-20"));
  it("labels days relative to now", () => {
    const now = new Date("2026-10-19T06:00:00Z");
    expect([dayLabel("2026-10-19", now), dayLabel("2026-10-20", now)]).toEqual(["Today", "Tomorrow"]);
    expect(dayLabel("2026-10-23", now)).toBe("Fri, 23 Oct");
  });
  it("makes initials without the Dr prefix", () => expect(initials("Dr. A. Sen")).toBe("AS"));
  it("counts down using the server clock, not the local one", () => {
    // local clock is 10 minutes ahead of the server; the hold has 8 minutes left by the server's clock
    const serverNow = Date.parse("2026-10-19T10:00:00Z");
    const localNow = serverNow + 10 * 60_000;
    expect(secondsLeft("2026-10-19T10:08:00Z", "2026-10-19T10:00:00Z", localNow, localNow)).toBe(480);
    expect(secondsLeft("2026-10-19T10:08:00Z", "2026-10-19T10:00:00Z", localNow, localNow + 481_000)).toBe(0);
  });
  it("pads mm:ss", () => expect(mmss(65)).toBe("01:05"));
});

import { addDays, dayParts } from "./format";
describe("date helpers", () => {
  it("adds days across month ends", () => expect(addDays("2026-10-30", 3)).toBe("2026-11-02"));
  it("splits a date card", () => expect(dayParts("2026-10-19")).toEqual({ weekday: "Mon", dom: "19" }));
});

import { windowProblem, windowSlots } from "./format";
describe("schedule helpers", () => {
  it("lists the slots of a window like the design preview", () =>
    expect(windowSlots("16:00", "17:00", 12)).toEqual(["4:00 pm", "4:12 pm", "4:24 pm", "4:36 pm", "4:48 pm"]));
  it("rejects windows the server would reject", () => {
    expect(windowProblem("16:00", "17:00", 12)).toBeNull();
    expect(windowProblem("16:00", "17:00", 25)).toMatch(/do not divide/);
    expect(windowProblem("17:00", "16:00", 12)).toMatch(/after start/);
  });
});
