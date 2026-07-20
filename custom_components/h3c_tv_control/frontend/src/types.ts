export interface HassEntity {
  entity_id: string;
  state: string;
  attributes: Record<string, unknown> & {
    friendly_name?: string;
    min?: number;
    max?: number;
    step?: number;
    options?: string[];
  };
}

export interface EntityRegistryEntry {
  entity_id: string;
  unique_id: string;
  device_id: string | null;
  platform?: string;
  disabled_by?: string | null;
}

export interface DeviceRegistryEntry {
  id: string;
  name?: string | null;
  name_by_user?: string | null;
  identifiers?: Array<[string, string]>;
  config_entries?: string[];
}

export interface HomeAssistant {
  language: string;
  states: Record<string, HassEntity>;
  callWS<T>(message: Record<string, unknown>): Promise<T>;
  callService(
    domain: string,
    service: string,
    data?: Record<string, unknown>,
  ): Promise<unknown>;
}

export interface CardConfig {
  type: "custom:h3c-tv-child-card";
  device_id: string;
  name?: string;
}
