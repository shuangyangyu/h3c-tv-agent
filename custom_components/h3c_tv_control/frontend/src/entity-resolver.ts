import type { DeviceRegistryEntry, EntityRegistryEntry } from "./types";

const DOMAIN = "h3c_tv_control";

export const ENTITY_SUFFIXES = [
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
] as const;

export type EntitySuffix = (typeof ENTITY_SUFFIXES)[number];
export type ResolvedEntities = Partial<Record<EntitySuffix, string>>;

/**
 * Resolve this card's entities by registry unique_id, not mutable entity names.
 * Longer suffixes are checked first to make overlapping names unambiguous.
 */
export function resolveDeviceEntities(
  entries: EntityRegistryEntry[],
  deviceId: string,
): ResolvedEntities {
  const suffixes = [...ENTITY_SUFFIXES].sort((a, b) => b.length - a.length);
  const resolved: ResolvedEntities = {};

  for (const entry of entries) {
    if (
      entry.device_id !== deviceId ||
      entry.platform !== "h3c_tv_control" ||
      entry.disabled_by
    ) {
      continue;
    }

    const suffix = suffixes.find((candidate) =>
      entry.unique_id.endsWith(`_${candidate}`),
    );
    if (suffix && !resolved[suffix]) {
      resolved[suffix] = entry.entity_id;
    }
  }

  return resolved;
}

/** Exclude the integration's hub, which has no per-TV internet entity. */
export function isH3cTvDevice(
  device: DeviceRegistryEntry,
  entries: EntityRegistryEntry[],
): boolean {
  return (
    Boolean(device.identifiers?.some(([domain]) => domain === DOMAIN)) &&
    Boolean(resolveDeviceEntities(entries, device.id).internet)
  );
}
