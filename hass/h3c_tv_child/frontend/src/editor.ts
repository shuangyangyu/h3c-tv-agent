import { LitElement, css, html, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import { isH3cTvDevice } from "./entity-resolver";
import type {
  CardConfig,
  DeviceRegistryEntry,
  EntityRegistryEntry,
  HomeAssistant,
} from "./types";

@customElement("h3c-tv-child-card-editor")
export class H3CTVChildCardEditor extends LitElement {
  @property({ attribute: false }) public hass?: HomeAssistant;
  @state() private config?: CardConfig;
  @state() private devices: DeviceRegistryEntry[] = [];
  @state() private loadError = false;
  private devicesLoaded = false;

  public setConfig(config: CardConfig): void {
    this.config = config;
  }

  protected willUpdate(): void {
    if (this.hass && !this.devicesLoaded) {
      this.devicesLoaded = true;
      void this.loadDevices();
    }
  }

  private async loadDevices(): Promise<void> {
    try {
      const [devices, entities] = await Promise.all([
        this.hass!.callWS<DeviceRegistryEntry[]>({
          type: "config/device_registry/list",
        }),
        this.hass!.callWS<EntityRegistryEntry[]>({
          type: "config/entity_registry/list",
        }),
      ]);
      this.devices = devices
        .filter((device) => isH3cTvDevice(device, entities))
        .sort((a, b) => this.deviceName(a).localeCompare(this.deviceName(b)));
      this.loadError = false;
    } catch {
      this.devices = [];
      this.loadError = true;
    }
  }

  private deviceName(device: DeviceRegistryEntry): string {
    return device.name_by_user || device.name || device.id;
  }

  private updateConfig(key: "device_id" | "name", value: string): void {
    if (!this.config) return;
    const config = { ...this.config, [key]: value || undefined };
    this.config = config;
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config },
        bubbles: true,
        composed: true,
      }),
    );
  }

  protected render() {
    if (!this.config) return nothing;
    const zh = this.hass?.language?.toLowerCase().startsWith("zh") ?? false;

    return html`
      <div class="field">
        <label for="device">
          ${zh ? "H3C TV Child 设备" : "H3C TV control device"}
        </label>
        <select
          id="device"
          .value=${this.config.device_id || ""}
          @change=${(event: Event) =>
            this.updateConfig(
              "device_id",
              (event.target as HTMLSelectElement).value,
            )}
        >
          <option value="" disabled>
            ${zh ? "请选择 H3C TV Child 设备" : "Select an H3C TV Child device"}
          </option>
          ${this.devices.map(
            (device) =>
              html`<option value=${device.id}>${this.deviceName(device)}</option>`,
          )}
        </select>
        <div class="hint">
          ${zh
            ? "请选择带有上网开关的 H3C 设备；真实电视实体在集成“配置”中绑定。"
            : "Select the H3C device with the internet switch. Bind the real TV entity in the integration options."}
        </div>
        ${this.loadError
          ? html`<div class="error">
              ${zh ? "无法加载设备列表" : "Unable to load devices"}
            </div>`
          : nothing}
      </div>
      <div class="field">
        <label for="name">${zh ? "标题（可选）" : "Title (optional)"}</label>
        <input
          id="name"
          type="text"
          .value=${this.config.name || ""}
          @input=${(event: Event) =>
            this.updateConfig("name", (event.target as HTMLInputElement).value)}
        />
      </div>
    `;
  }

  static styles = css`
    :host {
      display: block;
    }
    .field {
      margin: 16px 0;
    }
    label {
      display: block;
      margin-bottom: 6px;
      color: var(--primary-text-color);
    }
    select,
    input {
      box-sizing: border-box;
      width: 100%;
      min-height: 44px;
      padding: 0 12px;
      border: 1px solid var(--divider-color);
      border-radius: var(--ha-card-border-radius, 12px);
      color: var(--primary-text-color);
      background: var(--card-background-color);
      font: inherit;
    }
    .error {
      margin-top: 6px;
      color: var(--error-color);
    }
    .hint {
      margin-top: 6px;
      color: var(--secondary-text-color);
      font-size: 12px;
      line-height: 1.4;
    }
  `;
}

declare global {
  interface HTMLElementTagNameMap {
    "h3c-tv-child-card-editor": H3CTVChildCardEditor;
  }
}
