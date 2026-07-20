import { describe, expect, it } from "vitest";

import {
  isH3cTvDevice,
  resolveDeviceEntities,
} from "../src/entity-resolver";
import type { DeviceRegistryEntry, EntityRegistryEntry } from "../src/types";

function entry(
  entityId: string,
  uniqueId: string,
  deviceId = "tv-device",
  overrides: Partial<EntityRegistryEntry> = {},
): EntityRegistryEntry {
  return {
    entity_id: entityId,
    unique_id: uniqueId,
    device_id: deviceId,
    platform: "h3c_tv_control",
    disabled_by: null,
    ...overrides,
  };
}

describe("resolveDeviceEntities", () => {
  it("resolves every supported entity from unique_id suffixes", () => {
    const suffixes = [
      "internet",
      "child",
      "session_minutes",
      "daily_minutes",
      "cooldown_minutes",
      "window_preset",
      "daily_used",
      "session_remaining",
      "cooldown_remaining",
      "tv_on_today",
      "daily_reset",
    ];
    const entries = suffixes.map((suffix) =>
      entry(`${suffix}.living_room`, `entry_living_room_${suffix}`),
    );

    expect(resolveDeviceEntities(entries, "tv-device")).toEqual(
      Object.fromEntries(
        suffixes.map((suffix) => [suffix, `${suffix}.living_room`]),
      ),
    );
  });

  it("filters other devices, integrations, and disabled entities", () => {
    const entries = [
      entry("switch.correct", "entry_tv_internet"),
      entry("switch.other_device", "entry_tv_child", "another-device"),
      entry("number.other_platform", "entry_tv_daily_minutes", "tv-device", {
        platform: "template",
      }),
      entry("sensor.disabled", "entry_tv_daily_used", "tv-device", {
        disabled_by: "user",
      }),
    ];

    expect(resolveDeviceEntities(entries, "tv-device")).toEqual({
      internet: "switch.correct",
    });
  });

  it("requires an underscore-delimited suffix and keeps the first match", () => {
    const entries = [
      entry("sensor.not_a_match", "entry_tv_session_remaining_extra"),
      entry("sensor.first", "entry_tv_session_remaining"),
      entry("sensor.second", "another_tv_session_remaining"),
    ];

    expect(resolveDeviceEntities(entries, "tv-device")).toEqual({
      session_remaining: "sensor.first",
    });
  });
});

describe("isH3cTvDevice", () => {
  const tv: DeviceRegistryEntry = {
    id: "tv-device",
    identifiers: [["h3c_tv_control", "entry_living_room"]],
  };
  const hub: DeviceRegistryEntry = {
    id: "hub-device",
    identifiers: [["h3c_tv_control", "entry"]],
  };

  it("accepts only H3C devices with an internet entity", () => {
    const entries = [entry("switch.tv", "entry_living_room_internet")];

    expect(isH3cTvDevice(tv, entries)).toBe(true);
    expect(isH3cTvDevice(hub, entries)).toBe(false);
  });

  it("rejects a foreign device even if it has a matching entity", () => {
    const foreign: DeviceRegistryEntry = {
      id: "tv-device",
      identifiers: [["other_integration", "entry_living_room"]],
    };
    const entries = [entry("switch.tv", "entry_living_room_internet")];

    expect(isH3cTvDevice(foreign, entries)).toBe(false);
  });
});
