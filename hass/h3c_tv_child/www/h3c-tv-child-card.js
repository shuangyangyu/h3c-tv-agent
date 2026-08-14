const k = globalThis, W = k.ShadowRoot && (k.ShadyCSS === void 0 || k.ShadyCSS.nativeShadow) && "adoptedStyleSheets" in Document.prototype && "replace" in CSSStyleSheet.prototype, B = /* @__PURE__ */ Symbol(), K = /* @__PURE__ */ new WeakMap();
let ct = class {
  constructor(t, e, s) {
    if (this._$cssResult$ = !0, s !== B) throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");
    this.cssText = t, this.t = e;
  }
  get styleSheet() {
    let t = this.o;
    const e = this.t;
    if (W && t === void 0) {
      const s = e !== void 0 && e.length === 1;
      s && (t = K.get(e)), t === void 0 && ((this.o = t = new CSSStyleSheet()).replaceSync(this.cssText), s && K.set(e, t));
    }
    return t;
  }
  toString() {
    return this.cssText;
  }
};
const _t = (i) => new ct(typeof i == "string" ? i : i + "", void 0, B), ht = (i, ...t) => {
  const e = i.length === 1 ? i[0] : t.reduce((s, r, o) => s + ((n) => {
    if (n._$cssResult$ === !0) return n.cssText;
    if (typeof n == "number") return n;
    throw Error("Value passed to 'css' function must be a 'css' function result: " + n + ". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.");
  })(r) + i[o + 1], i[0]);
  return new ct(e, i, B);
}, bt = (i, t) => {
  if (W) i.adoptedStyleSheets = t.map((e) => e instanceof CSSStyleSheet ? e : e.styleSheet);
  else for (const e of t) {
    const s = document.createElement("style"), r = k.litNonce;
    r !== void 0 && s.setAttribute("nonce", r), s.textContent = e.cssText, i.appendChild(s);
  }
}, Y = W ? (i) => i : (i) => i instanceof CSSStyleSheet ? ((t) => {
  let e = "";
  for (const s of t.cssRules) e += s.cssText;
  return _t(e);
})(i) : i;
const { is: wt, defineProperty: At, getOwnPropertyDescriptor: xt, getOwnPropertyNames: Et, getOwnPropertySymbols: St, getPrototypeOf: Ct } = Object, z = globalThis, G = z.trustedTypes, Ot = G ? G.emptyScript : "", Pt = z.reactiveElementPolyfillSupport, T = (i, t) => i, L = { toAttribute(i, t) {
  switch (t) {
    case Boolean:
      i = i ? Ot : null;
      break;
    case Object:
    case Array:
      i = i == null ? i : JSON.stringify(i);
  }
  return i;
}, fromAttribute(i, t) {
  let e = i;
  switch (t) {
    case Boolean:
      e = i !== null;
      break;
    case Number:
      e = i === null ? null : Number(i);
      break;
    case Object:
    case Array:
      try {
        e = JSON.parse(i);
      } catch {
        e = null;
      }
  }
  return e;
} }, F = (i, t) => !wt(i, t), Q = { attribute: !0, type: String, converter: L, reflect: !1, useDefault: !1, hasChanged: F };
Symbol.metadata ??= /* @__PURE__ */ Symbol("metadata"), z.litPropertyMetadata ??= /* @__PURE__ */ new WeakMap();
let E = class extends HTMLElement {
  static addInitializer(t) {
    this._$Ei(), (this.l ??= []).push(t);
  }
  static get observedAttributes() {
    return this.finalize(), this._$Eh && [...this._$Eh.keys()];
  }
  static createProperty(t, e = Q) {
    if (e.state && (e.attribute = !1), this._$Ei(), this.prototype.hasOwnProperty(t) && ((e = Object.create(e)).wrapped = !0), this.elementProperties.set(t, e), !e.noAccessor) {
      const s = /* @__PURE__ */ Symbol(), r = this.getPropertyDescriptor(t, s, e);
      r !== void 0 && At(this.prototype, t, r);
    }
  }
  static getPropertyDescriptor(t, e, s) {
    const { get: r, set: o } = xt(this.prototype, t) ?? { get() {
      return this[e];
    }, set(n) {
      this[e] = n;
    } };
    return { get: r, set(n) {
      const d = r?.call(this);
      o?.call(this, n), this.requestUpdate(t, d, s);
    }, configurable: !0, enumerable: !0 };
  }
  static getPropertyOptions(t) {
    return this.elementProperties.get(t) ?? Q;
  }
  static _$Ei() {
    if (this.hasOwnProperty(T("elementProperties"))) return;
    const t = Ct(this);
    t.finalize(), t.l !== void 0 && (this.l = [...t.l]), this.elementProperties = new Map(t.elementProperties);
  }
  static finalize() {
    if (this.hasOwnProperty(T("finalized"))) return;
    if (this.finalized = !0, this._$Ei(), this.hasOwnProperty(T("properties"))) {
      const e = this.properties, s = [...Et(e), ...St(e)];
      for (const r of s) this.createProperty(r, e[r]);
    }
    const t = this[Symbol.metadata];
    if (t !== null) {
      const e = litPropertyMetadata.get(t);
      if (e !== void 0) for (const [s, r] of e) this.elementProperties.set(s, r);
    }
    this._$Eh = /* @__PURE__ */ new Map();
    for (const [e, s] of this.elementProperties) {
      const r = this._$Eu(e, s);
      r !== void 0 && this._$Eh.set(r, e);
    }
    this.elementStyles = this.finalizeStyles(this.styles);
  }
  static finalizeStyles(t) {
    const e = [];
    if (Array.isArray(t)) {
      const s = new Set(t.flat(1 / 0).reverse());
      for (const r of s) e.unshift(Y(r));
    } else t !== void 0 && e.push(Y(t));
    return e;
  }
  static _$Eu(t, e) {
    const s = e.attribute;
    return s === !1 ? void 0 : typeof s == "string" ? s : typeof t == "string" ? t.toLowerCase() : void 0;
  }
  constructor() {
    super(), this._$Ep = void 0, this.isUpdatePending = !1, this.hasUpdated = !1, this._$Em = null, this._$Ev();
  }
  _$Ev() {
    this._$ES = new Promise((t) => this.enableUpdating = t), this._$AL = /* @__PURE__ */ new Map(), this._$E_(), this.requestUpdate(), this.constructor.l?.forEach((t) => t(this));
  }
  addController(t) {
    (this._$EO ??= /* @__PURE__ */ new Set()).add(t), this.renderRoot !== void 0 && this.isConnected && t.hostConnected?.();
  }
  removeController(t) {
    this._$EO?.delete(t);
  }
  _$E_() {
    const t = /* @__PURE__ */ new Map(), e = this.constructor.elementProperties;
    for (const s of e.keys()) this.hasOwnProperty(s) && (t.set(s, this[s]), delete this[s]);
    t.size > 0 && (this._$Ep = t);
  }
  createRenderRoot() {
    const t = this.shadowRoot ?? this.attachShadow(this.constructor.shadowRootOptions);
    return bt(t, this.constructor.elementStyles), t;
  }
  connectedCallback() {
    this.renderRoot ??= this.createRenderRoot(), this.enableUpdating(!0), this._$EO?.forEach((t) => t.hostConnected?.());
  }
  enableUpdating(t) {
  }
  disconnectedCallback() {
    this._$EO?.forEach((t) => t.hostDisconnected?.());
  }
  attributeChangedCallback(t, e, s) {
    this._$AK(t, s);
  }
  _$ET(t, e) {
    const s = this.constructor.elementProperties.get(t), r = this.constructor._$Eu(t, s);
    if (r !== void 0 && s.reflect === !0) {
      const o = (s.converter?.toAttribute !== void 0 ? s.converter : L).toAttribute(e, s.type);
      this._$Em = t, o == null ? this.removeAttribute(r) : this.setAttribute(r, o), this._$Em = null;
    }
  }
  _$AK(t, e) {
    const s = this.constructor, r = s._$Eh.get(t);
    if (r !== void 0 && this._$Em !== r) {
      const o = s.getPropertyOptions(r), n = typeof o.converter == "function" ? { fromAttribute: o.converter } : o.converter?.fromAttribute !== void 0 ? o.converter : L;
      this._$Em = r;
      const d = n.fromAttribute(e, o.type);
      this[r] = d ?? this._$Ej?.get(r) ?? d, this._$Em = null;
    }
  }
  requestUpdate(t, e, s, r = !1, o) {
    if (t !== void 0) {
      const n = this.constructor;
      if (r === !1 && (o = this[t]), s ??= n.getPropertyOptions(t), !((s.hasChanged ?? F)(o, e) || s.useDefault && s.reflect && o === this._$Ej?.get(t) && !this.hasAttribute(n._$Eu(t, s)))) return;
      this.C(t, e, s);
    }
    this.isUpdatePending === !1 && (this._$ES = this._$EP());
  }
  C(t, e, { useDefault: s, reflect: r, wrapped: o }, n) {
    s && !(this._$Ej ??= /* @__PURE__ */ new Map()).has(t) && (this._$Ej.set(t, n ?? e ?? this[t]), o !== !0 || n !== void 0) || (this._$AL.has(t) || (this.hasUpdated || s || (e = void 0), this._$AL.set(t, e)), r === !0 && this._$Em !== t && (this._$Eq ??= /* @__PURE__ */ new Set()).add(t));
  }
  async _$EP() {
    this.isUpdatePending = !0;
    try {
      await this._$ES;
    } catch (e) {
      Promise.reject(e);
    }
    const t = this.scheduleUpdate();
    return t != null && await t, !this.isUpdatePending;
  }
  scheduleUpdate() {
    return this.performUpdate();
  }
  performUpdate() {
    if (!this.isUpdatePending) return;
    if (!this.hasUpdated) {
      if (this.renderRoot ??= this.createRenderRoot(), this._$Ep) {
        for (const [r, o] of this._$Ep) this[r] = o;
        this._$Ep = void 0;
      }
      const s = this.constructor.elementProperties;
      if (s.size > 0) for (const [r, o] of s) {
        const { wrapped: n } = o, d = this[r];
        n !== !0 || this._$AL.has(r) || d === void 0 || this.C(r, void 0, o, d);
      }
    }
    let t = !1;
    const e = this._$AL;
    try {
      t = this.shouldUpdate(e), t ? (this.willUpdate(e), this._$EO?.forEach((s) => s.hostUpdate?.()), this.update(e)) : this._$EM();
    } catch (s) {
      throw t = !1, this._$EM(), s;
    }
    t && this._$AE(e);
  }
  willUpdate(t) {
  }
  _$AE(t) {
    this._$EO?.forEach((e) => e.hostUpdated?.()), this.hasUpdated || (this.hasUpdated = !0, this.firstUpdated(t)), this.updated(t);
  }
  _$EM() {
    this._$AL = /* @__PURE__ */ new Map(), this.isUpdatePending = !1;
  }
  get updateComplete() {
    return this.getUpdateComplete();
  }
  getUpdateComplete() {
    return this._$ES;
  }
  shouldUpdate(t) {
    return !0;
  }
  update(t) {
    this._$Eq &&= this._$Eq.forEach((e) => this._$ET(e, this[e])), this._$EM();
  }
  updated(t) {
  }
  firstUpdated(t) {
  }
};
E.elementStyles = [], E.shadowRootOptions = { mode: "open" }, E[T("elementProperties")] = /* @__PURE__ */ new Map(), E[T("finalized")] = /* @__PURE__ */ new Map(), Pt?.({ ReactiveElement: E }), (z.reactiveElementVersions ??= []).push("2.1.2");
const q = globalThis, tt = (i) => i, R = q.trustedTypes, et = R ? R.createPolicy("lit-html", { createHTML: (i) => i }) : void 0, pt = "$lit$", _ = `lit$${Math.random().toFixed(9).slice(2)}$`, ut = "?" + _, Tt = `<${ut}>`, A = document, N = () => A.createComment(""), U = (i) => i === null || typeof i != "object" && typeof i != "function", X = Array.isArray, Nt = (i) => X(i) || typeof i?.[Symbol.iterator] == "function", V = `[ 	
\f\r]`, P = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g, it = /-->/g, st = />/g, b = RegExp(`>|${V}(?:([^\\s"'>=/]+)(${V}*=${V}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`, "g"), rt = /'/g, ot = /"/g, mt = /^(?:script|style|textarea|title)$/i, Ut = (i) => (t, ...e) => ({ _$litType$: i, strings: t, values: e }), u = Ut(1), C = /* @__PURE__ */ Symbol.for("lit-noChange"), c = /* @__PURE__ */ Symbol.for("lit-nothing"), nt = /* @__PURE__ */ new WeakMap(), w = A.createTreeWalker(A, 129);
function gt(i, t) {
  if (!X(i) || !i.hasOwnProperty("raw")) throw Error("invalid template strings array");
  return et !== void 0 ? et.createHTML(t) : t;
}
const Ht = (i, t) => {
  const e = i.length - 1, s = [];
  let r, o = t === 2 ? "<svg>" : t === 3 ? "<math>" : "", n = P;
  for (let d = 0; d < e; d++) {
    const a = i[d];
    let h, p, l = -1, f = 0;
    for (; f < a.length && (n.lastIndex = f, p = n.exec(a), p !== null); ) f = n.lastIndex, n === P ? p[1] === "!--" ? n = it : p[1] !== void 0 ? n = st : p[2] !== void 0 ? (mt.test(p[2]) && (r = RegExp("</" + p[2], "g")), n = b) : p[3] !== void 0 && (n = b) : n === b ? p[0] === ">" ? (n = r ?? P, l = -1) : p[1] === void 0 ? l = -2 : (l = n.lastIndex - p[2].length, h = p[1], n = p[3] === void 0 ? b : p[3] === '"' ? ot : rt) : n === ot || n === rt ? n = b : n === it || n === st ? n = P : (n = b, r = void 0);
    const y = n === b && i[d + 1].startsWith("/>") ? " " : "";
    o += n === P ? a + Tt : l >= 0 ? (s.push(h), a.slice(0, l) + pt + a.slice(l) + _ + y) : a + _ + (l === -2 ? d : y);
  }
  return [gt(i, o + (i[e] || "<?>") + (t === 2 ? "</svg>" : t === 3 ? "</math>" : "")), s];
};
class H {
  constructor({ strings: t, _$litType$: e }, s) {
    let r;
    this.parts = [];
    let o = 0, n = 0;
    const d = t.length - 1, a = this.parts, [h, p] = Ht(t, e);
    if (this.el = H.createElement(h, s), w.currentNode = this.el.content, e === 2 || e === 3) {
      const l = this.el.content.firstChild;
      l.replaceWith(...l.childNodes);
    }
    for (; (r = w.nextNode()) !== null && a.length < d; ) {
      if (r.nodeType === 1) {
        if (r.hasAttributes()) for (const l of r.getAttributeNames()) if (l.endsWith(pt)) {
          const f = p[n++], y = r.getAttribute(l).split(_), $ = /([.?@])?(.*)/.exec(f);
          a.push({ type: 1, index: o, name: $[2], strings: y, ctor: $[1] === "." ? Mt : $[1] === "?" ? kt : $[1] === "@" ? Lt : I }), r.removeAttribute(l);
        } else l.startsWith(_) && (a.push({ type: 6, index: o }), r.removeAttribute(l));
        if (mt.test(r.tagName)) {
          const l = r.textContent.split(_), f = l.length - 1;
          if (f > 0) {
            r.textContent = R ? R.emptyScript : "";
            for (let y = 0; y < f; y++) r.append(l[y], N()), w.nextNode(), a.push({ type: 2, index: ++o });
            r.append(l[f], N());
          }
        }
      } else if (r.nodeType === 8) if (r.data === ut) a.push({ type: 2, index: o });
      else {
        let l = -1;
        for (; (l = r.data.indexOf(_, l + 1)) !== -1; ) a.push({ type: 7, index: o }), l += _.length - 1;
      }
      o++;
    }
  }
  static createElement(t, e) {
    const s = A.createElement("template");
    return s.innerHTML = t, s;
  }
}
function O(i, t, e = i, s) {
  if (t === C) return t;
  let r = s !== void 0 ? e._$Co?.[s] : e._$Cl;
  const o = U(t) ? void 0 : t._$litDirective$;
  return r?.constructor !== o && (r?._$AO?.(!1), o === void 0 ? r = void 0 : (r = new o(i), r._$AT(i, e, s)), s !== void 0 ? (e._$Co ??= [])[s] = r : e._$Cl = r), r !== void 0 && (t = O(i, r._$AS(i, t.values), r, s)), t;
}
class Dt {
  constructor(t, e) {
    this._$AV = [], this._$AN = void 0, this._$AD = t, this._$AM = e;
  }
  get parentNode() {
    return this._$AM.parentNode;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  u(t) {
    const { el: { content: e }, parts: s } = this._$AD, r = (t?.creationScope ?? A).importNode(e, !0);
    w.currentNode = r;
    let o = w.nextNode(), n = 0, d = 0, a = s[0];
    for (; a !== void 0; ) {
      if (n === a.index) {
        let h;
        a.type === 2 ? h = new D(o, o.nextSibling, this, t) : a.type === 1 ? h = new a.ctor(o, a.name, a.strings, this, t) : a.type === 6 && (h = new Rt(o, this, t)), this._$AV.push(h), a = s[++d];
      }
      n !== a?.index && (o = w.nextNode(), n++);
    }
    return w.currentNode = A, r;
  }
  p(t) {
    let e = 0;
    for (const s of this._$AV) s !== void 0 && (s.strings !== void 0 ? (s._$AI(t, s, e), e += s.strings.length - 2) : s._$AI(t[e])), e++;
  }
}
class D {
  get _$AU() {
    return this._$AM?._$AU ?? this._$Cv;
  }
  constructor(t, e, s, r) {
    this.type = 2, this._$AH = c, this._$AN = void 0, this._$AA = t, this._$AB = e, this._$AM = s, this.options = r, this._$Cv = r?.isConnected ?? !0;
  }
  get parentNode() {
    let t = this._$AA.parentNode;
    const e = this._$AM;
    return e !== void 0 && t?.nodeType === 11 && (t = e.parentNode), t;
  }
  get startNode() {
    return this._$AA;
  }
  get endNode() {
    return this._$AB;
  }
  _$AI(t, e = this) {
    t = O(this, t, e), U(t) ? t === c || t == null || t === "" ? (this._$AH !== c && this._$AR(), this._$AH = c) : t !== this._$AH && t !== C && this._(t) : t._$litType$ !== void 0 ? this.$(t) : t.nodeType !== void 0 ? this.T(t) : Nt(t) ? this.k(t) : this._(t);
  }
  O(t) {
    return this._$AA.parentNode.insertBefore(t, this._$AB);
  }
  T(t) {
    this._$AH !== t && (this._$AR(), this._$AH = this.O(t));
  }
  _(t) {
    this._$AH !== c && U(this._$AH) ? this._$AA.nextSibling.data = t : this.T(A.createTextNode(t)), this._$AH = t;
  }
  $(t) {
    const { values: e, _$litType$: s } = t, r = typeof s == "number" ? this._$AC(t) : (s.el === void 0 && (s.el = H.createElement(gt(s.h, s.h[0]), this.options)), s);
    if (this._$AH?._$AD === r) this._$AH.p(e);
    else {
      const o = new Dt(r, this), n = o.u(this.options);
      o.p(e), this.T(n), this._$AH = o;
    }
  }
  _$AC(t) {
    let e = nt.get(t.strings);
    return e === void 0 && nt.set(t.strings, e = new H(t)), e;
  }
  k(t) {
    X(this._$AH) || (this._$AH = [], this._$AR());
    const e = this._$AH;
    let s, r = 0;
    for (const o of t) r === e.length ? e.push(s = new D(this.O(N()), this.O(N()), this, this.options)) : s = e[r], s._$AI(o), r++;
    r < e.length && (this._$AR(s && s._$AB.nextSibling, r), e.length = r);
  }
  _$AR(t = this._$AA.nextSibling, e) {
    for (this._$AP?.(!1, !0, e); t !== this._$AB; ) {
      const s = tt(t).nextSibling;
      tt(t).remove(), t = s;
    }
  }
  setConnected(t) {
    this._$AM === void 0 && (this._$Cv = t, this._$AP?.(t));
  }
}
class I {
  get tagName() {
    return this.element.tagName;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  constructor(t, e, s, r, o) {
    this.type = 1, this._$AH = c, this._$AN = void 0, this.element = t, this.name = e, this._$AM = r, this.options = o, s.length > 2 || s[0] !== "" || s[1] !== "" ? (this._$AH = Array(s.length - 1).fill(new String()), this.strings = s) : this._$AH = c;
  }
  _$AI(t, e = this, s, r) {
    const o = this.strings;
    let n = !1;
    if (o === void 0) t = O(this, t, e, 0), n = !U(t) || t !== this._$AH && t !== C, n && (this._$AH = t);
    else {
      const d = t;
      let a, h;
      for (t = o[0], a = 0; a < o.length - 1; a++) h = O(this, d[s + a], e, a), h === C && (h = this._$AH[a]), n ||= !U(h) || h !== this._$AH[a], h === c ? t = c : t !== c && (t += (h ?? "") + o[a + 1]), this._$AH[a] = h;
    }
    n && !r && this.j(t);
  }
  j(t) {
    t === c ? this.element.removeAttribute(this.name) : this.element.setAttribute(this.name, t ?? "");
  }
}
class Mt extends I {
  constructor() {
    super(...arguments), this.type = 3;
  }
  j(t) {
    this.element[this.name] = t === c ? void 0 : t;
  }
}
class kt extends I {
  constructor() {
    super(...arguments), this.type = 4;
  }
  j(t) {
    this.element.toggleAttribute(this.name, !!t && t !== c);
  }
}
class Lt extends I {
  constructor(t, e, s, r, o) {
    super(t, e, s, r, o), this.type = 5;
  }
  _$AI(t, e = this) {
    if ((t = O(this, t, e, 0) ?? c) === C) return;
    const s = this._$AH, r = t === c && s !== c || t.capture !== s.capture || t.once !== s.once || t.passive !== s.passive, o = t !== c && (s === c || r);
    r && this.element.removeEventListener(this.name, this, s), o && this.element.addEventListener(this.name, this, t), this._$AH = t;
  }
  handleEvent(t) {
    typeof this._$AH == "function" ? this._$AH.call(this.options?.host ?? this.element, t) : this._$AH.handleEvent(t);
  }
}
class Rt {
  constructor(t, e, s) {
    this.element = t, this.type = 6, this._$AN = void 0, this._$AM = e, this.options = s;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  _$AI(t) {
    O(this, t);
  }
}
const zt = q.litHtmlPolyfillSupport;
zt?.(H, D), (q.litHtmlVersions ??= []).push("3.3.3");
const It = (i, t, e) => {
  const s = e?.renderBefore ?? t;
  let r = s._$litPart$;
  if (r === void 0) {
    const o = e?.renderBefore ?? null;
    s._$litPart$ = r = new D(t.insertBefore(N(), o), o, void 0, e ?? {});
  }
  return r._$AI(i), r;
};
const Z = globalThis;
class S extends E {
  constructor() {
    super(...arguments), this.renderOptions = { host: this }, this._$Do = void 0;
  }
  createRenderRoot() {
    const t = super.createRenderRoot();
    return this.renderOptions.renderBefore ??= t.firstChild, t;
  }
  update(t) {
    const e = this.render();
    this.hasUpdated || (this.renderOptions.isConnected = this.isConnected), super.update(t), this._$Do = It(e, this.renderRoot, this.renderOptions);
  }
  connectedCallback() {
    super.connectedCallback(), this._$Do?.setConnected(!0);
  }
  disconnectedCallback() {
    super.disconnectedCallback(), this._$Do?.setConnected(!1);
  }
  render() {
    return C;
  }
}
S._$litElement$ = !0, S.finalized = !0, Z.litElementHydrateSupport?.({ LitElement: S });
const jt = Z.litElementPolyfillSupport;
jt?.({ LitElement: S });
(Z.litElementVersions ??= []).push("4.2.2");
const ft = (i) => (t, e) => {
  e !== void 0 ? e.addInitializer(() => {
    customElements.define(i, t);
  }) : customElements.define(i, t);
};
const Vt = { attribute: !0, type: String, converter: L, reflect: !1, hasChanged: F }, Wt = (i = Vt, t, e) => {
  const { kind: s, metadata: r } = e;
  let o = globalThis.litPropertyMetadata.get(r);
  if (o === void 0 && globalThis.litPropertyMetadata.set(r, o = /* @__PURE__ */ new Map()), s === "setter" && ((i = Object.create(i)).wrapped = !0), o.set(e.name, i), s === "accessor") {
    const { name: n } = e;
    return { set(d) {
      const a = t.get.call(this);
      t.set.call(this, d), this.requestUpdate(n, a, i, !0, d);
    }, init(d) {
      return d !== void 0 && this.C(n, void 0, i, d), d;
    } };
  }
  if (s === "setter") {
    const { name: n } = e;
    return function(d) {
      const a = this[n];
      t.call(this, d), this.requestUpdate(n, a, i, !0, d);
    };
  }
  throw Error("Unsupported decorator location: " + s);
};
function J(i) {
  return (t, e) => typeof e == "object" ? Wt(i, t, e) : ((s, r, o) => {
    const n = r.hasOwnProperty(o);
    return r.constructor.createProperty(o, s), n ? Object.getOwnPropertyDescriptor(r, o) : void 0;
  })(i, t, e);
}
function g(i) {
  return J({ ...i, state: !0, attribute: !1 });
}
const Bt = "h3c_tv_child", Ft = [
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
  "daily_reset"
];
function vt(i, t) {
  const e = [...Ft].sort((r, o) => o.length - r.length), s = {};
  for (const r of i) {
    if (r.device_id !== t || r.platform !== "h3c_tv_child" || r.disabled_by)
      continue;
    const o = e.find(
      (n) => r.unique_id.endsWith(`_${n}`)
    );
    o && !s[o] && (s[o] = r.entity_id);
  }
  return s;
}
function yt(i, t) {
  return !!i.identifiers?.some(([e]) => e === Bt) && !!vt(t, i.id).internet;
}
var qt = Object.defineProperty, Xt = Object.getOwnPropertyDescriptor, M = (i, t, e, s) => {
  for (var r = s > 1 ? void 0 : s ? Xt(t, e) : t, o = i.length - 1, n; o >= 0; o--)
    (n = i[o]) && (r = (s ? n(t, e, r) : n(r)) || r);
  return s && r && qt(t, e, r), r;
};
let x = class extends S {
  constructor() {
    super(...arguments), this.devices = [], this.loadError = !1, this.devicesLoaded = !1;
  }
  setConfig(i) {
    this.config = i;
  }
  willUpdate() {
    this.hass && !this.devicesLoaded && (this.devicesLoaded = !0, this.loadDevices());
  }
  async loadDevices() {
    try {
      const [i, t] = await Promise.all([
        this.hass.callWS({
          type: "config/device_registry/list"
        }),
        this.hass.callWS({
          type: "config/entity_registry/list"
        })
      ]);
      this.devices = i.filter((e) => yt(e, t)).sort((e, s) => this.deviceName(e).localeCompare(this.deviceName(s))), this.loadError = !1;
    } catch {
      this.devices = [], this.loadError = !0;
    }
  }
  deviceName(i) {
    return i.name_by_user || i.name || i.id;
  }
  updateConfig(i, t) {
    if (!this.config) return;
    const e = { ...this.config, [i]: t || void 0 };
    this.config = e, this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: e },
        bubbles: !0,
        composed: !0
      })
    );
  }
  render() {
    if (!this.config) return c;
    const i = this.hass?.language?.toLowerCase().startsWith("zh") ?? !1;
    return u`
      <div class="field">
        <label for="device">
          ${i ? "H3C TV Child 设备" : "H3C TV control device"}
        </label>
        <select
          id="device"
          .value=${this.config.device_id || ""}
          @change=${(t) => this.updateConfig(
      "device_id",
      t.target.value
    )}
        >
          <option value="" disabled>
            ${i ? "请选择 H3C TV Child 设备" : "Select an H3C TV Child device"}
          </option>
          ${this.devices.map(
      (t) => u`<option value=${t.id}>${this.deviceName(t)}</option>`
    )}
        </select>
        <div class="hint">
          ${i ? "请选择带有上网开关的 H3C 设备；真实电视实体在集成“配置”中绑定。" : "Select the H3C device with the internet switch. Bind the real TV entity in the integration options."}
        </div>
        ${this.loadError ? u`<div class="error">
              ${i ? "无法加载设备列表" : "Unable to load devices"}
            </div>` : c}
      </div>
      <div class="field">
        <label for="name">${i ? "标题（可选）" : "Title (optional)"}</label>
        <input
          id="name"
          type="text"
          .value=${this.config.name || ""}
          @input=${(t) => this.updateConfig("name", t.target.value)}
        />
      </div>
    `;
  }
};
x.styles = ht`
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
M([
  J({ attribute: !1 })
], x.prototype, "hass", 2);
M([
  g()
], x.prototype, "config", 2);
M([
  g()
], x.prototype, "devices", 2);
M([
  g()
], x.prototype, "loadError", 2);
x = M([
  ft("h3c-tv-child-card-editor")
], x);
var Zt = Object.defineProperty, Jt = Object.getOwnPropertyDescriptor, v = (i, t, e, s) => {
  for (var r = s > 1 ? void 0 : s ? Jt(t, e) : t, o = i.length - 1, n; o >= 0; o--)
    (n = i[o]) && (r = (s ? n(t, e, r) : n(r)) || r);
  return s && r && Zt(t, e, r), r;
};
const at = /* @__PURE__ */ new Set(["unavailable", "unknown"]), dt = /* @__PURE__ */ new Set([
  "on",
  "idle",
  "playing",
  "paused",
  "buffering"
]), lt = {
  zh: {
    defaultTitle: "电视儿童上网",
    online: "设备在线",
    offline: "设备不可用",
    tvOn: "电视开启",
    tvOff: "电视关闭",
    tvUnbound: "未绑定 media_player",
    tvPower: "电视电源",
    internet: "上网",
    child: "儿童控制",
    session: "本次剩余",
    daily: "今日使用",
    tvOnToday: "今日电视开启",
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
    nighttime: "夜间（20:00–08:00）"
  },
  en: {
    defaultTitle: "TV child internet",
    online: "Device online",
    offline: "Device unavailable",
    tvOn: "TV on",
    tvOff: "TV off",
    tvUnbound: "No media_player bound",
    tvPower: "TV power",
    internet: "Internet",
    child: "Child control",
    session: "Session remaining",
    daily: "Used today",
    tvOnToday: "TV on today",
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
    nighttime: "Nighttime (20:00–08:00)"
  }
};
let m = class extends S {
  constructor() {
    super(...arguments), this.entities = {}, this.deviceName = "", this.loading = !0, this.loadError = !1, this.actionError = "", this.busy = /* @__PURE__ */ new Set(), this.optimisticOn = {}, this.resetArmed = !1, this.loadedDeviceId = "";
  }
  static async getConfigElement() {
    return document.createElement("h3c-tv-child-card-editor");
  }
  static async getStubConfig(i) {
    try {
      const [t, e] = await Promise.all([
        i.callWS({
          type: "config/device_registry/list"
        }),
        i.callWS({
          type: "config/entity_registry/list"
        })
      ]);
      return { type: "custom:h3c-tv-child-card", device_id: t.find(
        (r) => yt(r, e)
      )?.id || "" };
    } catch {
      return { type: "custom:h3c-tv-child-card", device_id: "" };
    }
  }
  setConfig(i) {
    if (!i.device_id)
      throw new Error("device_id is required");
    this.config = { ...i, type: "custom:h3c-tv-child-card" }, this.loadedDeviceId !== i.device_id && (this.loadedDeviceId = "", this.entities = {}, this.loading = !0);
  }
  getCardSize() {
    return 5;
  }
  updated(i) {
    if ((i.has("hass") || i.has("config")) && this.startEntityLoad(), i.has("hass") && this.hass && Object.keys(this.optimisticOn).length) {
      const t = { ...this.optimisticOn };
      let e = !1;
      for (const [s, r] of Object.entries(t)) {
        const o = this.hass.states[s];
        !o || at.has(o.state) || o.state === "on" === r && (delete t[s], e = !0);
      }
      e && (this.optimisticOn = t);
    }
  }
  startEntityLoad() {
    if (!this.hass || !this.config || this.loadedDeviceId === this.config.device_id || this.loadPromise)
      return;
    const i = this.config.device_id;
    this.loadPromise = this.loadEntities().finally(() => {
      this.loadPromise = void 0, this.config?.device_id !== i && this.startEntityLoad();
    });
  }
  disconnectedCallback() {
    super.disconnectedCallback(), this.resetTimer && window.clearTimeout(this.resetTimer);
  }
  get words() {
    return lt[this.hass?.language?.toLowerCase().startsWith("zh") ? "zh" : "en"];
  }
  async loadEntities() {
    const i = this.config.device_id;
    this.loading = !0;
    try {
      const [t, e] = await Promise.all([
        this.hass.callWS({
          type: "config/entity_registry/list"
        }),
        this.hass.callWS({
          type: "config/device_registry/list"
        })
      ]);
      if (this.config?.device_id !== i) return;
      this.entities = vt(t, i);
      const s = e.find((r) => r.id === i);
      this.deviceName = s?.name_by_user || s?.name || "", this.loadedDeviceId = i, this.loadError = !1;
    } catch {
      this.loadError = !0;
    } finally {
      this.loading = !1;
    }
  }
  entity(i) {
    const t = this.entities[i];
    return t ? this.hass?.states[t] : void 0;
  }
  usable(i) {
    return !!i && !at.has(i.state);
  }
  numberState(i) {
    const t = this.entity(i);
    if (!this.usable(t)) return;
    const e = Number(t.state);
    return Number.isFinite(e) ? e : void 0;
  }
  async call(i, t, e, s) {
    if (!(!this.hass || this.busy.has(i))) {
      this.busy = new Set(this.busy).add(i), this.actionError = "";
      try {
        await this.hass.callService(t, e, s);
      } catch (r) {
        const o = r instanceof Error ? r.message : String(r);
        this.actionError = `${this.words.serviceFailed}: ${o}`;
      } finally {
        const r = new Set(this.busy);
        r.delete(i), this.busy = r;
      }
    }
  }
  toggle(i) {
    const t = this.entity(i);
    if (!this.usable(t) || !this.hass) return;
    const e = this.isOn(i);
    if (i === "internet") {
      this.optimisticOn = {
        ...this.optimisticOn,
        [t.entity_id]: !e
      }, this.hass.callService("switch", e ? "turn_off" : "turn_on", {
        entity_id: t.entity_id
      }).catch((s) => {
        const r = s instanceof Error ? s.message : String(s);
        this.actionError = `${this.words.serviceFailed}: ${r}`;
        const o = { ...this.optimisticOn };
        delete o[t.entity_id], this.optimisticOn = o;
      });
      return;
    }
    this.call(
      i,
      "switch",
      e ? "turn_off" : "turn_on",
      { entity_id: t.entity_id }
    );
  }
  isOn(i) {
    const t = this.entity(i);
    if (!t) return !1;
    const e = this.optimisticOn[t.entity_id];
    return e !== void 0 ? e : t.state === "on";
  }
  toggleMediaPlayer(i) {
    if (typeof i != "string") return;
    const t = this.hass?.states[i];
    if (!this.usable(t)) return;
    const e = dt.has(t.state);
    this.call(
      "media_player",
      "media_player",
      e ? "turn_off" : "turn_on",
      { entity_id: i }
    );
  }
  setNumber(i, t) {
    const e = this.entity(i), s = Number(t.target.value);
    e && Number.isFinite(s) && this.call(i, "number", "set_value", {
      entity_id: e.entity_id,
      value: s
    });
  }
  selectWindow(i) {
    const t = this.entity("window_preset");
    t && this.call("window_preset", "select", "select_option", {
      entity_id: t.entity_id,
      option: i.target.value
    });
  }
  resetDaily() {
    if (!this.resetArmed) {
      this.resetArmed = !0, this.resetTimer = window.setTimeout(() => {
        this.resetArmed = !1;
      }, 5e3);
      return;
    }
    this.resetArmed = !1;
    const i = this.entity("daily_reset");
    i && this.call("daily_reset", "button", "press", {
      entity_id: i.entity_id
    });
  }
  switchControl(i, t) {
    const e = this.entity(i), s = this.usable(e), r = this.isOn(i), o = !s || i !== "internet" && this.busy.has(i);
    return u`
      <button
        class="switch-row"
        aria-label=${t}
        aria-pressed=${r}
        ?disabled=${o}
        @click=${() => this.toggle(i)}
      >
        <span>${t}</span>
        <span class="toggle ${r ? "on" : ""}" aria-hidden="true"
          ><span></span
        ></span>
      </button>
    `;
  }
  mediaPlayerControl(i) {
    const t = typeof i == "string" ? this.hass?.states[i] : void 0, e = this.usable(t), s = !!t && dt.has(t.state);
    return u`
      <button
        class="switch-row"
        aria-label=${this.words.tvPower}
        aria-pressed=${s}
        ?disabled=${!e || this.busy.has("media_player")}
        @click=${() => this.toggleMediaPlayer(i)}
      >
        <span>${this.words.tvPower}</span>
        <span class="toggle ${s ? "on" : ""}" aria-hidden="true"
          ><span></span
        ></span>
      </button>
    `;
  }
  progress(i, t, e, s = !1) {
    const o = t !== void 0 && e !== void 0 && e > 0 ? Math.max(0, Math.min(100, t / e * 100)) : 0;
    return u`
      <div class="metric">
        <div class="metric-head">
          <span>${i}</span>
          <strong>
            ${t === void 0 ? this.words.unavailable : `${this.formatNumber(t)} ${this.words.minutes}`}
          </strong>
        </div>
        <div
          class="progress"
          role="progressbar"
          aria-valuemin="0"
          aria-valuemax=${e ?? 0}
          aria-valuenow=${t ?? 0}
        >
          <span style=${`width:${o}%`}></span>
        </div>
      </div>
    `;
  }
  formatNumber(i) {
    return new Intl.NumberFormat(this.hass?.language || "en", {
      maximumFractionDigits: 1
    }).format(i);
  }
  reasonText(i) {
    const t = String(i || "");
    if (this.words === lt.zh || !t) return t;
    const e = {
      不在允许上网时间段: "Outside the allowed time window",
      已超出允许上网时间段: "Outside the allowed time window",
      今日上网时长已用完: "Daily internet limit reached",
      单次用满后仍在冷却: "Session cooldown is active",
      单次上网时长已到: "Session limit reached"
    }, s = t.match(/单次用满后冷却中，还需 (\d+) 分钟/);
    return e[t] || (s ? `Cooling down; ${s[1]} min remaining` : t);
  }
  numberInput(i, t) {
    const e = this.entity(i);
    return u`
      <label class="setting">
        <span>${t}</span>
        <span class="input-unit">
          <input
            type="number"
            .value=${this.usable(e) ? e.state : ""}
            min=${String(e?.attributes.min ?? 0)}
            max=${String(e?.attributes.max ?? 999)}
            step=${String(e?.attributes.step ?? 1)}
            ?disabled=${!this.usable(e) || this.busy.has(i)}
            @change=${(s) => this.setNumber(i, s)}
          />
          <small>${this.words.minutes}</small>
        </span>
      </label>
    `;
  }
  render() {
    if (this.loading)
      return u`<ha-card><div class="message"><ha-icon icon="mdi:loading"></ha-icon></div></ha-card>`;
    if (this.loadError)
      return u`<ha-card><div class="message error">${this.words.loadFailed}</div></ha-card>`;
    const i = this.entity("internet"), t = this.entity("child"), e = this.usable(i), s = i?.attributes.tv_active, r = i?.attributes.media_player_entity_id, o = this.numberState("session_minutes"), n = this.numberState("daily_minutes"), d = this.numberState("session_remaining"), a = this.numberState("daily_used"), h = this.numberState("tv_on_today"), p = this.numberState("cooldown_remaining"), l = this.reasonText(i?.attributes.disable_reason), f = this.config?.name || this.deviceName || i?.attributes.friendly_name || this.words.defaultTitle, y = !i || !t, $ = this.entity("window_preset"), $t = $?.attributes.options || ["all_day", "daytime", "nighttime"];
    return u`
      <ha-card>
        <div class="card">
          <header>
            <div>
              <h2>${f}</h2>
              <div class="chips">
                <span class="chip ${e ? "good" : "bad"}">
                  ${e ? this.words.online : this.words.offline}
                </span>
                <span class="chip">
                  ${r ? s === !0 ? this.words.tvOn : this.words.tvOff : this.words.tvUnbound}
                </span>
              </div>
            </div>
            <ha-icon icon=${s ? "mdi:television" : "mdi:television-off"}></ha-icon>
          </header>

          ${y ? u`<div class="notice">${this.words.missing}</div>` : c}
          ${r ? c : u`<div class="notice">${this.words.tvUnbound}</div>`}

          <div class="switches">
            ${this.mediaPlayerControl(r)}
            ${this.switchControl("internet", this.words.internet)}
            ${this.switchControl("child", this.words.child)}
          </div>

          <div class="metrics">
            ${this.progress(this.words.session, d, o, !0)}
            ${this.progress(this.words.daily, a, n)}
            <div class="duration">
              <ha-icon icon="mdi:television"></ha-icon>
              <span>${this.words.tvOnToday}</span>
              <strong>
                ${h === void 0 ? this.words.unavailable : `${this.formatNumber(h)} ${this.words.minutes}`}
              </strong>
            </div>
            <div class="cooldown">
              <ha-icon icon="mdi:snowflake"></ha-icon>
              <span>${this.words.cooldown}</span>
              <strong>
                ${p === void 0 ? this.words.unavailable : p > 0 ? `${this.formatNumber(p)} ${this.words.minutes}` : this.words.disabled}
              </strong>
            </div>
          </div>

          ${l ? u`<div class="reason">
                <ha-icon icon="mdi:information-outline"></ha-icon>
                <span><b>${this.words.reason}:</b> ${l}</span>
              </div>` : c}
          ${this.actionError ? u`<div class="error action">${this.actionError}</div>` : c}

          <details>
            <summary>${this.words.settings}</summary>
            <div class="settings">
              ${this.numberInput("session_minutes", this.words.sessionLimit)}
              ${this.numberInput("daily_minutes", this.words.dailyLimit)}
              ${this.numberInput("cooldown_minutes", this.words.cooldownLimit)}
              <label class="setting">
                <span>${this.words.window}</span>
                <select
                  .value=${$?.state || ""}
                  ?disabled=${!this.usable($) || this.busy.has("window_preset")}
                  @change=${this.selectWindow}
                >
                  ${$t.map(
      (j) => u`<option value=${j}>
                        ${this.words[j] || j}
                      </option>`
    )}
                </select>
              </label>
              <button
                class="reset ${this.resetArmed ? "confirm" : ""}"
                ?disabled=${!this.usable(this.entity("daily_reset")) || this.busy.has("daily_reset")}
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
};
m.styles = ht`
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
      grid-template-columns: repeat(3, minmax(0, 1fr));
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
    .cooldown,
    .duration {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      min-height: 28px;
    }
    .metric-head strong,
    .cooldown strong,
    .duration strong {
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
    .cooldown,
    .duration {
      justify-content: flex-start;
      min-height: 44px;
      padding: 0 10px;
      border-radius: 10px;
      background: var(--secondary-background-color);
    }
    .cooldown strong,
    .duration strong {
      margin-left: auto;
    }
    .cooldown ha-icon,
    .duration ha-icon,
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
v([
  J({ attribute: !1 })
], m.prototype, "hass", 2);
v([
  g()
], m.prototype, "config", 2);
v([
  g()
], m.prototype, "entities", 2);
v([
  g()
], m.prototype, "deviceName", 2);
v([
  g()
], m.prototype, "loading", 2);
v([
  g()
], m.prototype, "loadError", 2);
v([
  g()
], m.prototype, "actionError", 2);
v([
  g()
], m.prototype, "busy", 2);
v([
  g()
], m.prototype, "optimisticOn", 2);
v([
  g()
], m.prototype, "resetArmed", 2);
m = v([
  ft("h3c-tv-child-card")
], m);
window.customCards = window.customCards || [];
window.customCards.some((i) => i.type === "h3c-tv-child-card") || window.customCards.push({
  type: "h3c-tv-child-card",
  name: "H3C TV Child Card",
  description: "Single-TV internet and child-control card",
  preview: !0
});
export {
  m as H3CTVChildCard
};
