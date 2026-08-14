// @vitest-environment happy-dom

import { afterEach, describe, expect, it, vi } from "vitest";

import { H3CTVChildCard } from "../src/h3c-tv-child-card";
import type {
  DeviceRegistryEntry,
  EntityRegistryEntry,
  HassEntity,
  HomeAssistant,
} from "../src/types";

const DEVICE_ID = "living-room-tv";
const SUFFIXES = [
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

const registryEntries: EntityRegistryEntry[] = SUFFIXES.map((suffix) => ({
  entity_id: `${entityDomain(suffix)}.living_room_${suffix}`,
  unique_id: `entry_living_room_${suffix}`,
  device_id: DEVICE_ID,
  platform: "h3c_tv_child",
  disabled_by: null,
}));

const devices: DeviceRegistryEntry[] = [
  {
    id: DEVICE_ID,
    name: "Living room TV",
    identifiers: [["h3c_tv_child", "entry_living_room"]],
  },
];

function entityDomain(suffix: (typeof SUFFIXES)[number]): string {
  if (suffix === "internet" || suffix === "child") return "switch";
  if (suffix.endsWith("_minutes")) return "number";
  if (suffix === "window_preset") return "select";
  if (suffix === "daily_reset") return "button";
  return "sensor";
}

function makeStates(
  bound = true,
  mediaPlayerState = "off",
): Record<string, HassEntity> {
  const states: Record<string, HassEntity> = {};
  const values: Record<(typeof SUFFIXES)[number], string> = {
    internet: "off",
    child: "on",
    session_minutes: "30",
    daily_minutes: "90",
    cooldown_minutes: "60",
    window_preset: "daytime",
    daily_used: "15",
    session_remaining: "20",
    cooldown_remaining: "0",
    tv_on_today: "75",
    daily_reset: "2026-07-20T07:00:00+00:00",
  };

  for (const entry of registryEntries) {
    const suffix = SUFFIXES.find((candidate) =>
      entry.unique_id.endsWith(`_${candidate}`),
    )!;
    states[entry.entity_id] = {
      entity_id: entry.entity_id,
      state: values[suffix],
      attributes:
        suffix === "internet"
          ? {
              friendly_name: "Living room internet",
              media_player_entity_id: bound
                ? "media_player.living_room"
                : null,
              tv_active: true,
            }
          : suffix.endsWith("_minutes")
            ? { min: 5, max: 480, step: 5 }
            : suffix === "window_preset"
              ? { options: ["all_day", "daytime", "nighttime"] }
              : {},
    };
  }
  if (bound) {
    states["media_player.living_room"] = {
      entity_id: "media_player.living_room",
      state: mediaPlayerState,
      attributes: { friendly_name: "Living room TV" },
    };
  }
  return states;
}

function makeHass(options?: {
  bound?: boolean;
  mediaPlayerState?: string;
  registryFailure?: boolean;
  serviceFailure?: Error;
}): {
  hass: HomeAssistant;
  callService: ReturnType<typeof vi.fn>;
} {
  const callService = options?.serviceFailure
    ? vi.fn().mockRejectedValue(options.serviceFailure)
    : vi.fn().mockResolvedValue(undefined);

  const hass: HomeAssistant = {
    language: "en",
    states: makeStates(
      options?.bound ?? true,
      options?.mediaPlayerState ?? "off",
    ),
    callWS: async <T>(message: Record<string, unknown>): Promise<T> => {
      if (message.type === "config/entity_registry/list") {
        if (options?.registryFailure) throw new Error("registry unavailable");
        return registryEntries as T;
      }
      if (message.type === "config/device_registry/list") {
        return devices as T;
      }
      throw new Error(`Unexpected WS command: ${String(message.type)}`);
    },
    callService,
  };
  return { hass, callService };
}

async function mountCard(hass: HomeAssistant): Promise<H3CTVChildCard> {
  const card = new H3CTVChildCard();
  card.setConfig({
    type: "custom:h3c-tv-child-card",
    device_id: DEVICE_ID,
  });
  card.hass = hass;
  document.body.append(card);
  await vi.waitFor(() => {
    expect(card.shadowRoot?.querySelector(".card, .message.error")).toBeTruthy();
  });
  return card;
}

function change(control: HTMLInputElement | HTMLSelectElement, value: string) {
  control.value = value;
  control.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
}

afterEach(() => {
  document.body.replaceChildren();
  vi.restoreAllMocks();
});

describe("h3c-tv-child-card interactions", () => {
  it("calls the correct services for TV, internet, and child switches", async () => {
    const { hass, callService } = makeHass();
    const card = await mountCard(hass);

    (
      card.shadowRoot!.querySelector(
        '.switch-row[aria-label="TV power"]',
      ) as HTMLButtonElement
    ).click();
    await vi.waitFor(() =>
      expect(callService).toHaveBeenCalledWith("media_player", "turn_on", {
        entity_id: "media_player.living_room",
      }),
    );

    (
      card.shadowRoot!.querySelector(
        '.switch-row[aria-label="Internet"]',
      ) as HTMLButtonElement
    ).click();
    await vi.waitFor(() =>
      expect(callService).toHaveBeenCalledWith("switch", "turn_on", {
        entity_id: "switch.living_room_internet",
      }),
    );

    (
      card.shadowRoot!.querySelector(
        '.switch-row[aria-label="Child control"]',
      ) as HTMLButtonElement
    ).click();
    await vi.waitFor(() =>
      expect(callService).toHaveBeenCalledWith("switch", "turn_off", {
        entity_id: "switch.living_room_child",
      }),
    );
  });

  it("turns off a TV whose media player is active", async () => {
    const { hass, callService } = makeHass({
      mediaPlayerState: "playing",
    });
    const card = await mountCard(hass);

    card.shadowRoot!.querySelector<HTMLButtonElement>(
      '.switch-row[aria-label="TV power"]',
    )!.click();

    await vi.waitFor(() =>
      expect(callService).toHaveBeenCalledWith("media_player", "turn_off", {
        entity_id: "media_player.living_room",
      }),
    );
  });

  it("calls standard services for all settings and confirmed daily reset", async () => {
    const { hass, callService } = makeHass();
    const card = await mountCard(hass);
    const root = card.shadowRoot!;
    const inputs = [...root.querySelectorAll<HTMLInputElement>('input[type="number"]')];

    change(inputs[0], "45");
    change(inputs[1], "120");
    change(inputs[2], "30");
    change(root.querySelector<HTMLSelectElement>(".setting select")!, "nighttime");

    const firstReset = root.querySelector<HTMLButtonElement>(".reset")!;
    firstReset.click();
    await card.updateComplete;
    expect(
      callService.mock.calls.filter((call) => call[0] === "button"),
    ).toHaveLength(0);
    root.querySelector<HTMLButtonElement>(".reset")!.click();

    await vi.waitFor(() => expect(callService).toHaveBeenCalledTimes(5));
    expect(callService.mock.calls).toEqual(
      expect.arrayContaining([
        [
          "number",
          "set_value",
          { entity_id: "number.living_room_session_minutes", value: 45 },
        ],
        [
          "number",
          "set_value",
          { entity_id: "number.living_room_daily_minutes", value: 120 },
        ],
        [
          "number",
          "set_value",
          { entity_id: "number.living_room_cooldown_minutes", value: 30 },
        ],
        [
          "select",
          "select_option",
          {
            entity_id: "select.living_room_window_preset",
            option: "nighttime",
          },
        ],
        [
          "button",
          "press",
          { entity_id: "button.living_room_daily_reset" },
        ],
      ]),
    );
  });

  it("shows a warning when no media_player is bound", async () => {
    const card = await mountCard(makeHass({ bound: false }).hass);

    expect(card.shadowRoot!.textContent).toContain("No media_player bound");
  });

  it("shows today's total TV power-on time", async () => {
    const card = await mountCard(makeHass().hass);

    expect(card.shadowRoot!.textContent).toContain("TV on today");
    expect(card.shadowRoot!.textContent).toContain("75 min");
  });

  it("shows an entity loading error when the registry request fails", async () => {
    const card = await mountCard(makeHass({ registryFailure: true }).hass);

    expect(card.shadowRoot!.textContent).toContain(
      "Unable to load entities for this device",
    );
  });

  it("shows the service error returned by Home Assistant", async () => {
    const { hass } = makeHass({
      serviceFailure: new Error("permission denied"),
    });
    const card = await mountCard(hass);
    card.shadowRoot!.querySelector<HTMLButtonElement>(
      '.switch-row[aria-label="Internet"]',
    )!.click();

    await vi.waitFor(() => {
      expect(card.shadowRoot!.textContent).toContain(
        "Operation failed: permission denied",
      );
    });
  });

  it("loads the latest device when selection changes during a registry request", async () => {
    const secondDeviceId = "bedroom-tv";
    const secondEntries: EntityRegistryEntry[] = ["internet", "child"].map(
      (suffix) => ({
        entity_id: `switch.bedroom_${suffix}`,
        unique_id: `entry_bedroom_${suffix}`,
        device_id: secondDeviceId,
        platform: "h3c_tv_child",
        disabled_by: null,
      }),
    );
    const allEntries = [...registryEntries, ...secondEntries];
    const allDevices = [
      ...devices,
      {
        id: secondDeviceId,
        name: "Bedroom TV",
        identifiers: [["h3c_tv_child", "entry_bedroom"]] as [
          string,
          string,
        ][],
      },
    ];
    let resolveFirstRequest: (
      entries: EntityRegistryEntry[],
    ) => void = () => undefined;
    let entityRequestCount = 0;
    const hass: HomeAssistant = {
      language: "en",
      states: {
        ...makeStates(),
        "switch.bedroom_internet": {
          entity_id: "switch.bedroom_internet",
          state: "on",
          attributes: {},
        },
        "switch.bedroom_child": {
          entity_id: "switch.bedroom_child",
          state: "off",
          attributes: {},
        },
      },
      callWS: async <T>(message: Record<string, unknown>): Promise<T> => {
        if (message.type === "config/entity_registry/list") {
          entityRequestCount += 1;
          if (entityRequestCount === 1) {
            return new Promise<EntityRegistryEntry[]>((resolve) => {
              resolveFirstRequest = resolve;
            }) as Promise<T>;
          }
          return allEntries as T;
        }
        if (message.type === "config/device_registry/list") {
          return allDevices as T;
        }
        throw new Error(`Unexpected WS command: ${String(message.type)}`);
      },
      callService: vi.fn().mockResolvedValue(undefined),
    };
    const card = new H3CTVChildCard();
    card.setConfig({
      type: "custom:h3c-tv-child-card",
      device_id: DEVICE_ID,
    });
    card.hass = hass;
    document.body.append(card);
    await vi.waitFor(() => expect(entityRequestCount).toBe(1));

    card.setConfig({
      type: "custom:h3c-tv-child-card",
      device_id: secondDeviceId,
    });
    resolveFirstRequest(allEntries);

    await vi.waitFor(() => {
      expect(card.shadowRoot?.textContent).toContain("Bedroom TV");
    });
    expect(entityRequestCount).toBe(2);
  });
});
