// MetaFlora News: web push alerts (bell + preferences panel).
// Nothing loads from Firebase and no permission is requested until the reader turns alerts on.
// Readers are anonymous: Firebase anonymous sign-in gives this browser a random ID; we store that ID,
// the push token and the reader's choices. No name, email or browsing history.

const cfgEl = document.getElementById("mfn-push-config");
const bell = document.getElementById("mfn-bell");
const panel = document.getElementById("mfn-panel");
if (cfgEl && bell && panel) init(JSON.parse(cfgEl.textContent));

function init(CFG) {
  const SDK = `https://www.gstatic.com/firebasejs/${CFG.sdk}`;
  const KEY = "mfn-push";
  const form = panel.querySelector("form");
  const status = panel.querySelector("#mfn-status");
  const views = [...panel.querySelectorAll("[data-v]")];
  const btn = (a) => panel.querySelector(`[data-act="${a}"]`);
  let busy = false;

  // ---------- local state (survives reloads; the server copy is the source of truth for sending)
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; } };
  const store = (s) => { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch {} };
  let st = Object.assign({ enabled: false, topics: CFG.defaults.topics, freq: CFG.defaults.freq }, load());

  // ---------- capabilities
  const ua = navigator.userAgent;
  const ios = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  const supported = window.isSecureContext && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  const perm = () => ("Notification" in window ? Notification.permission : "unsupported");
  const platform = () => {
    const kind = ios ? "ios" : /Android/.test(ua) ? "android" : "desktop";
    const b = /Edg\//.test(ua) ? "edge" : /Firefox\//.test(ua) ? "firefox" : /Chrome\//.test(ua) ? "chrome" : /Safari\//.test(ua) ? "safari" : "other";
    return `${kind}-${b}${standalone ? "-app" : ""}`.slice(0, 40);
  };

  // ---------- Firebase, loaded on demand
  let fbp = null;
  function firebase() {
    if (!fbp) fbp = (async () => {
      const [app, auth, fs] = await Promise.all([
        import(`${SDK}/firebase-app.js`), import(`${SDK}/firebase-auth.js`), import(`${SDK}/firebase-firestore.js`)]);
      const a = app.getApps().find((x) => x.name === "[DEFAULT]") || app.initializeApp(CFG.firebase);
      const au = auth.getAuth(a);
      await auth.signInAnonymously(au);
      return { app: a, uid: au.currentUser.uid, db: fs.getFirestore(a), fs };
    })().catch((e) => { fbp = null; throw e; });
    return fbp;
  }
  async function messaging(app) {
    const m = await import(`${SDK}/firebase-messaging.js`);
    if (!(await m.isSupported())) throw new Error("unsupported");
    return { m, msg: m.getMessaging(app) };
  }
  async function swReg() {
    const reg = await navigator.serviceWorker.register("/firebase-messaging-sw.js", { scope: "/" });
    await navigator.serviceWorker.ready;
    return reg;
  }

  // ---------- form <-> state
  function readForm() {
    const fd = new FormData(form);
    const freq = fd.get("freq") || "all";
    let topics = fd.getAll("topic");
    if (freq === "breaking" && !topics.includes("breaking")) topics = ["breaking", ...topics];
    return { freq, topics };
  }
  function fillForm() {
    form.querySelectorAll('input[name="freq"]').forEach((i) => (i.checked = i.value === st.freq));
    form.querySelectorAll('input[name="topic"]').forEach((i) => (i.checked = st.topics.includes(i.value)));
    syncTopics();
  }
  function syncTopics() {
    const brk = form.querySelector('input[name="freq"]:checked')?.value === "breaking";
    form.querySelectorAll('input[name="topic"]').forEach((i) => {
      const off = brk && i.value !== "breaking";
      i.closest("label").classList.toggle("is-muted", off);
      if (brk && i.value === "breaking") i.checked = true;
    });
  }

  // ---------- view
  function say(text) { status.textContent = text; }
  function render() {
    let v = "prefs";
    if (!supported) v = ios && !standalone ? "ios" : "unsupported";
    else if (ios && !standalone) v = "ios";
    else if (perm() === "denied") v = "denied";
    views.forEach((el) => (el.hidden = el.dataset.v !== v));
    const on = st.enabled && perm() === "granted";
    btn("enable").hidden = on;
    btn("save").hidden = !on;
    btn("disable").hidden = !on;
    bell.classList.toggle("is-on", on);
    bell.setAttribute("aria-label", `News alerts: ${on ? "on" : "off"}`);
    if (v === "prefs") {
      const n = st.topics.filter((t) => t !== "breaking").length;
      const what = st.freq === "breaking" ? "breaking news only" : st.freq === "digest" ? `a daily digest, ${n} topic${n === 1 ? "" : "s"}` : `new stories in ${n} topic${n === 1 ? "" : "s"}`;
      say(on ? `Alerts are on for this device: ${what}${st.topics.includes("breaking") && st.freq !== "breaking" ? " plus breaking news" : ""}.` : "Alerts are off on this device.");
    } else if (v === "denied") say("Alerts are blocked in this browser's settings.");
    else if (v === "ios") say("Add MetaFlora News to your Home Screen to get alerts.");
    else say("This browser can't receive alerts.");
  }

  // ---------- actions
  async function enable() {
    const { freq, topics } = readForm();
    if (!topics.length) return say("Choose at least one topic.");
    const p = await Notification.requestPermission();   // only ever called from a click
    if (p !== "granted") { render(); return say(p === "denied" ? "Alerts are blocked in this browser's settings." : "Permission was not granted."); }
    say("Turning on alerts…");
    const fb = await firebase();
    const reg = await swReg();
    const { m, msg } = await messaging(fb.app);
    const token = await m.getToken(msg, { vapidKey: CFG.vapidKey, serviceWorkerRegistration: reg });
    if (!token) throw new Error("no token");
    const ref = fb.fs.doc(fb.db, "devices", fb.uid);
    const now = fb.fs.serverTimestamp();
    const base = { uid: fb.uid, token, topics, freq, enabled: true, platform: platform(), updated: now };
    const snap = await fb.fs.getDoc(ref);
    if (snap.exists()) await fb.fs.updateDoc(ref, base);
    else await fb.fs.setDoc(ref, { ...base, created: now });
    st = { enabled: true, topics, freq, refreshed: Date.now() };
    store(st); render();
    say("Alerts are on. We'll notify this device when a story matches your choices.");
  }
  async function save() {
    const { freq, topics } = readForm();
    if (!topics.length) return say("Choose at least one topic.");
    const fb = await firebase();
    await fb.fs.updateDoc(fb.fs.doc(fb.db, "devices", fb.uid), { topics, freq, platform: platform(), updated: fb.fs.serverTimestamp() });
    st = { ...st, topics, freq }; store(st); render(); say("Preferences saved.");
  }
  async function disable(quiet) {
    st = { ...st, enabled: false }; store(st);
    try {
      const fb = await firebase();
      await fb.fs.deleteDoc(fb.fs.doc(fb.db, "devices", fb.uid));
      try { const { m, msg } = await messaging(fb.app); await m.deleteToken(msg); } catch {}
    } finally { render(); if (!quiet) say("Alerts are off. We won't send this device anything."); }
  }
  async function run(fn) {
    if (busy) return; busy = true;
    panel.setAttribute("aria-busy", "true");
    try { await fn(); }
    catch (e) {
      const msg = String(e && (e.code || e.message || e));
      say(msg.includes("permission-denied") ? "Please wait a few seconds and try again." :
          msg.includes("unsupported") ? "This browser can't receive alerts." :
          "Something went wrong. Please try again in a moment.");
      console.warn("[mfn-push]", e);
    } finally { busy = false; panel.removeAttribute("aria-busy"); }
  }

  // ---------- panel open/close, keyboard
  function open() { fillForm(); render(); panel.hidden = false; bell.setAttribute("aria-expanded", "true"); panel.querySelector("h2").focus(); }
  function close(focusBell = true) { panel.hidden = true; bell.setAttribute("aria-expanded", "false"); if (focusBell) bell.focus(); }
  bell.addEventListener("click", () => (panel.hidden ? open() : close()));
  panel.querySelector(".mfn-x").addEventListener("click", () => close());
  panel.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  document.addEventListener("click", (e) => { if (!panel.hidden && !panel.contains(e.target) && !bell.contains(e.target)) close(false); });
  form.addEventListener("change", (e) => { if (e.target.name === "freq") syncTopics(); });
  form.addEventListener("submit", (e) => { e.preventDefault(); run(enable); });
  btn("save").addEventListener("click", () => run(save));
  btn("disable").addEventListener("click", () => run(() => disable(false)));

  // ---------- on every page: keep an enabled device healthy, count notification clicks
  render();
  if (st.enabled && supported) {
    if (perm() !== "granted") run(() => disable(true));          // permission revoked in browser settings
    else if (Date.now() - (st.refreshed || 0) > 7 * 864e5) {      // weekly token refresh
      run(async () => {
        const fb = await firebase(); const reg = await swReg(); const { m, msg } = await messaging(fb.app);
        const token = await m.getToken(msg, { vapidKey: CFG.vapidKey, serviceWorkerRegistration: reg });
        await fb.fs.updateDoc(fb.fs.doc(fb.db, "devices", fb.uid), { token, updated: fb.fs.serverTimestamp() });
        st.refreshed = Date.now(); store(st);
      });
    }
  }
  const q = new URLSearchParams(location.search);
  if (q.get("utm_source") === "push" && q.get("utm_campaign")) {
    const key = q.get("utm_campaign").slice(0, 120);
    ["utm_source", "utm_medium", "utm_campaign"].forEach((k) => q.delete(k));
    history.replaceState(null, "", location.pathname + (q.toString() ? `?${q}` : "") + location.hash);
    firebase().then((fb) => fb.fs.setDoc(fb.fs.doc(fb.db, "clicks", `${key}__${fb.uid}`), { key, uid: fb.uid, at: fb.fs.serverTimestamp() }))
      .catch(() => {});  // already counted, or offline: never matters to the reader
  }
}
