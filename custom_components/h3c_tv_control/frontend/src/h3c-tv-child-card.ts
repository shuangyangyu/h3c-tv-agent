import { LitElement, css, html, nothing, type PropertyValues } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import "./editor";
import {
  isH3cTvDevice,
  resolveDeviceEntities,
  type EntitySuffix,
  type ResolvedEntities,
} from "./entity-resolver";
import type {
  CardConfig,
  DeviceRegistryEntry,
  EntityRegistryEntry,
  HassEntity,
  HomeAssistant,
} from "./types";

const UNAVAILABLE = new Set(["unavailable", "unknown"]);

const TEXT = {
  zh: {
    defaultTitle: "电视儿童上网",
    online: "设备在线",
    offline: "设备不可用",
    tvOn: "电视开启",
    tvOff: "电视关闭",
    tvUnbound: "未绑定 media_player",
    internet: "上网",
    child: "儿童控制",
    session: "本次剩余",
    daily: "今日使用",
    cooldown: "冷却剩余",
    minutes: "分钟",
    disabled: "未启用",
    unavailable: "不可用",
    reason: "停用原因",
    settings: "儿童控制设置",
    sessionLimit: "单次允许",
    dailyLimit: "每日允许",
    cooldownLimit: "冷却时间",
    window: "允许时段",
    reset: "今日初始化",
    confirmReset: "再次点击确认",
    loadFailed: "无法加载该设备的实体",
    missing: "设备实体不完整，请重新加载集成",
    serviceFailed: "操作失败",
    all_day: "全天",
    daytime: "白天（08:00–20:00）",
    nighttime: "夜间（20:00–08:00）",
  },
  en: {
    defaultTitle: "TV child internet",
    online: "Device online",
    offline: "Device unavailable",
    tvOn: "TV on",
    tvOff: "TV off",
    tvUnbound: "No media_player bound",
    internet: "Internet",
    child: "Child control",
    session: "Session remaining",
    daily: "Used today",
    cooldown: "Cooldown remaining",
    minutes: "min",
    disabled: "Not enabled",
    unavailable: "Unavailable",
    reason: "Disabled because",
    settings: "Child control settings",
    sessionLimit: "Session limit",
    dailyLimit: "Daily limit",
    cooldownLimit: "Cooldown",
    window: "Allowed window",
    reset: "Reset today",
    confirmReset: "Click again to confirm",
    loadFailed: "Unable to load entities for this device",
    missing: "Device entities are incomplete; reload the integration",
    serviceFailed: "Operation failed",
    all_day: "All day",
    daytime: "Daytime (08:00–20:00)",
    nighttime: "Nighttime (20:00–08:00)",
  },
} as const;

@customElement("h3c-tv-child-card")
export class H3CTVChildCard extends LitElement {
  @property({ attribute: false }) public hass?: HomeAssistant;
  @state() private config?: CardConfig;
  @state() private entities: ResolvedEntities = {};
  @state() private deviceName = "";
  @state() private loading = true;
  @state() private loadError = false;
  @state() private actionError = "";
  @state() private busy = new Set<string>();
  @state() private resetArmed = false;
  private loadedDeviceId = "";
  private loadPromise?: Promise<void>;
  private resetTimer?: number;

  public static async getConfigElement(): Promise<HTMLElement> {
    return document.createElement("h3c-tv-child-card-editor");
  }

  public static async getStubConfig(hass: HomeAssistant): Promise<CardConfig> {
    try {
      const [devices, entities] = await Promise.all([
        hass.callWS<DeviceRegistryEntry[]>({
          type: "config/device_registry/list",
        }),
        hass.callWS<EntityRegistryEntry[]>({
          type: "config/entity_registry/list",
        }),
      ]);
      const device = devices.find((candidate) =>
        isH3cTvDevice(candidate, entities),
      );
      return { type: "custom:h3c-tv-child-card", device_id: device?.id || "" };
    } catch {
      return { type: "custom:h3c-tv-child-card", device_id: "" };
    }
  }

  public setConfig(config: CardConfig): void {
    if (!config.device_id) {
      throw new Error("device_id is required");
    }
    this.config = { ...config, type: "custom:h3c-tv-child-card" };
    if (this.loadedDeviceId !== config.device_id) {
      this.loadedDeviceId = "";
      this.entities = {};
      this.loading = true;
    }
  }

  public getCardSize(): number {
    return 5;
  }

  protected updated(changed: PropertyValues): void {
    if (
      (changed.has("hass") || changed.has("config")) &&
      this.hass &&
      this.config &&
      this.loadedDeviceId !== this.config.device_id &&
      !this.loadPromise
    ) {
      this.loadPromise = this.loadEntities().finally(() => {
        this.loadPromise = undefined;
      });
    }
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    if (this.resetTimer) window.clearTimeout(this.resetTimer);
  }

  private get words() {
    return TEXT[this.hass?.language?.toLowerCase().startsWith("zh") ? "zh" : "en"];
  }

  private async loadEntities(): Promise<void> {
    const deviceId = this.config!.device_id;
    this.loading = true;
    try {
      const [entries, devices] = await Promise.all([
        this.hass!.callWS<EntityRegistryEntry[]>({
          type: "config/entity_registry/list",
        }),
        this.hass!.callWS<DeviceRegistryEntry[]>({
          type: "config/device_registry/list",
        }),
      ]);
      if (this.config?.device_id !== deviceId) return;
      this.entities = resolveDeviceEntities(entries, deviceId);
      const device = devices.find((candidate) => candidate.id === deviceId);
      this.deviceName = device?.name_by_user || device?.name || "";
      this.loadedDeviceId = deviceId;
      this.loadError = false;
    } catch {
      this.loadError = true;
    } finally {
      this.loading = false;
    }
  }

  private entity(suffix: EntitySuffix): HassEntity | undefined {
    const entityId = this.entities[suffix];
    return entityId ? this.hass?.states[entityId] : undefined;
  }

  private usable(entity?: HassEntity): boolean {
    return !!entity && !UNAVAILABLE.has(entity.state);
  }

  private numberState(suffix: EntitySuffix): number | undefined {
    const entity = this.entity(suffix);
    if (!this.usable(entity)) return undefined;
    const value = Number(entity!.state);
    return Number.isFinite(value) ? value : undefined;
  }

  private async call(
    key: string,
    domain: string,
    service: string,
    data: Record<string, unknown>,
  ): Promise<void> {
    if (!this.hass || this.busy.has(key)) return;
    this.busy = new Set(this.busy).add(key);
    this.actionError = "";
    try {
      await this.hass.callService(domain, service, data);
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      this.actionError = `${this.words.serviceFailed}: ${detail}`;
    } finally {
      const busy = new Set(this.busy);
      busy.delete(key);
      this.busy = busy;
    }
  }

  private toggle(suffix: "internet" | "child"): void {
    const entity = this.entity(suffix);
    if (!this.usable(entity)) return;
    void this.call(
      suffix,
      "switch",
      entity!.state === "on" ? "turn_off" : "turn_on",
      { entity_id: entity!.entity_id },
    );
  }

  private setNumber(suffix: EntitySuffix, event: Event): void {
    const entity = this.entity(suffix);
    const value = Number((event.target as HTMLInputElement).value);
    if (entity && Number.isFinite(value)) {
      void this.call(suffix, "number", "set_value", {
        entity_id: entity.entity_id,
        value,
      });
    }
  }

  private selectWindow(event: Event): void {
    const entity = this.entity("window_preset");
    if (entity) {
      void this.call("window_preset", "select", "select_option", {
        entity_id: entity.entity_id,
        option: (event.target as HTMLSelectElement).value,
      });
    }
  }

  private resetDaily(): void {
    if (!this.resetArmed) {
      this.resetArmed = true;
      this.resetTimer = window.setTimeout(() => {
        this.resetArmed = false;
      }, 5000);
      return;
    }
    this.resetArmed = false;
    const entity = this.entity("daily_reset");
    if (entity) {
      void this.call("daily_reset", "button", "press", {
        entity_id: entity.entity_id,
      });
    }
  }

  private switchControl(suffix: "internet" | "child", label: string) {
    const entity = this.entity(suffix);
    const available = this.usable(entity);
    const on = entity?.state === "on";
    return html`
      <button
        class="switch-row"
        aria-label=${label}
        aria-pressed=${on}
        ?disabled=${!available || this.busy.has(suffix)}
        @click=${() => this.toggle(suffix)}
      >
        <span>${label}</span>
        <span class="toggle ${on ? "on" : ""}" aria-hidden="true"
          ><span></span
        ></span>
      </button>
    `;
  }

  private progress(
    label: string,
    value: number | undefined,
    max: number | undefined,
    remaining = false,
  ) {
    const valid = value !== undefined && max !== undefined && max > 0;
    const ratio = valid
      ? Math.max(0, Math.min(100, (remaining ? value / max : value / max) * 100))
      : 0;
    return html`
      <div class="metric">
        <div class="metric-head">
          <span>${label}</span>
          <strong>
            ${value === undefined
              ? this.words.unavailable
              : `${this.formatNumber(value)} ${this.words.minutes}`}
          </strong>
        </div>
        <div
          class="progress"
          role="progressbar"
          aria-valuemin="0"
          aria-valuemax=${max ?? 0}
          aria-valuenow=${value ?? 0}
        >
          <span style=${`width:${ratio}%`}></span>
        </div>
      </div>
    `;
  }

  private formatNumber(value: number): string {
    return new Intl.NumberFormat(this.hass?.language || "en", {
      maximumFractionDigits: 1,
    }).format(value);
  }

  private reasonText(reason: unknown): string {
    const value = String(reason || "");
    if (this.words === TEXT.zh || !value) return value;
    const exact: Record<string, string> = {
      "不在允许上网时间段": "Outside the allowed time window",
      "已超出允许上网时间段": "Outside the allowed time window",
      "今日上网时长已用完": "Daily internet limit reached",
      "单次用满后仍在冷却": "Session cooldown is active",
      "单次上网时长已到": "Session limit reached",
    };
    const cooldown = value.match(/单次用满后冷却中，还需 (\d+) 分钟/);
    return exact[value] || (cooldown ? `Cooling down; ${cooldown[1]} min remaining` : value);
  }

  private numberInput(suffix: EntitySuffix, label: string) {
    const entity = this.entity(suffix);
    return html`
      <label class="setting">
        <span>${label}</span>
        <span class="input-unit">
          <input
            type="number"
            .value=${this.usable(entity) ? entity!.state : ""}
            min=${String(entity?.attributes.min ?? 0)}
            max=${String(entity?.attributes.max ?? 999)}
            step=${String(entity?.attributes.step ?? 1)}
            ?disabled=${!this.usable(entity) || this.busy.has(suffix)}
            @change=${(event: Event) => this.setNumber(suffix, event)}
          />
          <small>${this.words.minutes}</small>
        </span>
      </label>
    `;
  }

  protected render() {
    if (this.loading) {
      return html`<ha-card><div class="message"><ha-icon icon="mdi:loading"></ha-icon></div></ha-card>`;
    }
    if (this.loadError) {
      return html`<ha-card><div class="message error">${this.words.loadFailed}</div></ha-card>`;
    }

    const internet = this.entity("internet");
    const child = this.entity("child");
    const online = this.usable(internet);
    const tvActive = internet?.attributes.tv_active;
    const mediaPlayer = internet?.attributes.media_player_entity_id;
    const sessionLimit = this.numberState("session_minutes");
    const dailyLimit = this.numberState("daily_minutes");
    const sessionRemaining = this.numberState("session_remaining");
    const dailyUsed = this.numberState("daily_used");
    const cooldown = this.numberState("cooldown_remaining");
    const reason = this.reasonText(internet?.attributes.disable_reason);
    const title =
      this.config?.name ||
      this.deviceName ||
      internet?.attributes.friendly_name ||
      this.words.defaultTitle;
    const missingCore = !internet || !child;
    const windowEntity = this.entity("window_preset");
    const options =
      (windowEntity?.attributes.options as string[] | undefined) ||
      ["all_day", "daytime", "nighttime"];

    return html`
      <ha-card>
        <div class="card">
          <header>
            <div>
              <h2>${title}</h2>
              <div class="chips">
                <span class="chip ${online ? "good" : "bad"}">
                  ${online ? this.words.online : this.words.offline}
                </span>
                <span class="chip">
                  ${!mediaPlayer
                    ? this.words.tvUnbound
                    : tvActive === true
                      ? this.words.tvOn
                      : this.words.tvOff}
                </span>
              </div>
            </div>
            <ha-icon icon=${tvActive ? "mdi:television" : "mdi:television-off"}></ha-icon>
          </header>

          ${missingCore ? html`<div class="notice">${this.words.missing}</div>` : nothing}
          ${!mediaPlayer ? html`<div class="notice">${this.words.tvUnbound}</div>` : nothing}

          <div class="switches">
            ${this.switchControl("internet", this.words.internet)}
            ${this.switchControl("child", this.words.child)}
          </div>

          <div class="metrics">
            ${this.progress(this.words.session, sessionRemaining, sessionLimit, true)}
            ${this.progress(this.words.daily, dailyUsed, dailyLimit)}
            <div class="cooldown">
              <ha-icon icon="mdi:snowflake"></ha-icon>
              <span>${this.words.cooldown}</span>
              <strong>
                ${cooldown === undefined
                  ? this.words.unavailable
                  : cooldown > 0
                    ? `${this.formatNumber(cooldown)} ${this.words.minutes}`
                    : this.words.disabled}
              </strong>
            </div>
          </div>

          ${reason
            ? html`<div class="reason">
                <ha-icon icon="mdi:information-outline"></ha-icon>
                <span><b>${this.words.reason}:</b> ${reason}</span>
              </div>`
            : nothing}
          ${this.actionError ? html`<div class="error action">${this.actionError}</div>` : nothing}

          <details>
            <summary>${this.words.settings}</summary>
            <div class="settings">
              ${this.numberInput("session_minutes", this.words.sessionLimit)}
              ${this.numberInput("daily_minutes", this.words.dailyLimit)}
              ${this.numberInput("cooldown_minutes", this.words.cooldownLimit)}
              <label class="setting">
                <span>${this.words.window}</span>
                <select
                  .value=${windowEntity?.state || ""}
                  ?disabled=${!this.usable(windowEntity) ||
                  this.busy.has("window_preset")}
                  @change=${this.selectWindow}
                >
                  ${options.map(
                    (option) =>
                      html`<option value=${option}>
                        ${this.words[option as keyof typeof this.words] || option}
                      </option>`,
                  )}
                </select>
              </label>
              <button
                class="reset ${this.resetArmed ? "confirm" : ""}"
                ?disabled=${!this.usable(this.entity("daily_reset")) ||
                this.busy.has("daily_reset")}
                @click=${this.resetDaily}
              >
                <ha-icon icon="mdi:calendar-refresh"></ha-icon>
                ${this.resetArmed ? this.words.confirmReset : this.words.reset}
              </button>
            </div>
          </details>
        </div>
      </ha-card>
    `;
  }

  static styles = css`
    :host {
      display: block;
      color: var(--primary-text-color);
    }
    ha-card {
      overflow: hidden;
    }
    .card {
      padding: 20px;
    }
    header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
    }
    header > ha-icon {
      --mdc-icon-size: 34px;
      color: var(--state-icon-color, var(--primary-color));
    }
    h2 {
      margin: 0 0 8px;
      font-size: 20px;
      line-height: 1.25;
    }
    .chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .chip {
      padding: 3px 8px;
      border-radius: 999px;
      color: var(--secondary-text-color);
      background: var(--secondary-background-color);
      font-size: 12px;
    }
    .chip.good {
      color: var(--success-color, #43a047);
    }
    .chip.bad,
    .error {
      color: var(--error-color);
    }
    .switches {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 20px;
    }
    button,
    select,
    input,
    summary {
      font: inherit;
    }
    .switch-row {
      display: flex;
      min-height: 48px;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding: 0 12px;
      border: 1px solid var(--divider-color);
      border-radius: 12px;
      color: var(--primary-text-color);
      background: var(--card-background-color);
      cursor: pointer;
    }
    button:disabled,
    select:disabled,
    input:disabled {
      cursor: default;
      opacity: 0.5;
    }
    .toggle {
      position: relative;
      width: 38px;
      height: 22px;
      flex: 0 0 auto;
      border-radius: 11px;
      background: var(--disabled-color);
      transition: background 0.2s;
    }
    .toggle span {
      position: absolute;
      top: 3px;
      left: 3px;
      width: 16px;
      height: 16px;
      border-radius: 50%;
      background: var(--text-primary-color, white);
      transition: transform 0.2s;
    }
    .toggle.on {
      background: var(--primary-color);
    }
    .toggle.on span {
      transform: translateX(16px);
    }
    .metrics {
      display: grid;
      gap: 14px;
    }
    .metric-head,
    .cooldown {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      min-height: 28px;
    }
    .metric-head strong,
    .cooldown strong {
      font-size: 13px;
    }
    .progress {
      height: 7px;
      overflow: hidden;
      border-radius: 4px;
      background: var(--divider-color);
    }
    .progress span {
      display: block;
      height: 100%;
      border-radius: inherit;
      background: var(--primary-color);
      transition: width 0.25s;
    }
    .cooldown {
      justify-content: flex-start;
      min-height: 44px;
      padding: 0 10px;
      border-radius: 10px;
      background: var(--secondary-background-color);
    }
    .cooldown strong {
      margin-left: auto;
    }
    .cooldown ha-icon,
    .reason ha-icon {
      --mdc-icon-size: 20px;
      color: var(--primary-color);
    }
    .notice,
    .reason,
    .action {
      margin: 10px 0;
      padding: 10px 12px;
      border-radius: 10px;
      background: var(--secondary-background-color);
      font-size: 13px;
    }
    .reason {
      display: flex;
      align-items: flex-start;
      gap: 8px;
    }
    details {
      margin-top: 14px;
      border-top: 1px solid var(--divider-color);
    }
    summary {
      display: flex;
      min-height: 44px;
      align-items: center;
      cursor: pointer;
      color: var(--primary-color);
    }
    .settings {
      display: grid;
      gap: 10px;
      padding-top: 4px;
    }
    .setting {
      display: flex;
      min-height: 46px;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .input-unit {
      display: flex;
      align-items: center;
      gap: 6px;
    }
    input,
    select {
      box-sizing: border-box;
      min-height: 44px;
      padding: 0 10px;
      border: 1px solid var(--divider-color);
      border-radius: 8px;
      color: var(--primary-text-color);
      background: var(--card-background-color);
    }
    input {
      width: 92px;
    }
    select {
      max-width: 210px;
    }
    small {
      color: var(--secondary-text-color);
    }
    .reset {
      min-height: 44px;
      border: 1px solid var(--error-color);
      border-radius: 10px;
      color: var(--error-color);
      background: transparent;
      cursor: pointer;
    }
    .reset.confirm {
      color: var(--text-primary-color, white);
      background: var(--error-color);
    }
    .message {
      display: flex;
      min-height: 100px;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    @media (max-width: 480px) {
      .card {
        padding: 16px;
      }
      .switches {
        grid-template-columns: 1fr;
      }
      .setting {
        align-items: flex-start;
        flex-direction: column;
      }
      .setting input,
      .setting select,
      .input-unit {
        width: 100%;
        max-width: none;
      }
    }
  `;
}

declare global {
  interface Window {
    customCards?: Array<Record<string, unknown>>;
  }
  interface HTMLElementTagNameMap {
    "h3c-tv-child-card": H3CTVChildCard;
  }
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "h3c-tv-child-card")) {
  window.customCards.push({
    type: "h3c-tv-child-card",
    name: "H3C TV Child Card",
    description: "Single-TV internet and child-control card",
    preview: true,
  });
}
