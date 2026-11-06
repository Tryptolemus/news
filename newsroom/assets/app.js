// MetaFlora News as an installable app (PWA): registers the service worker on every page and runs the
// "Get the app" button, the phone install bar and the desktop QR panel.
// Chrome, Edge, Samsung Internet and Brave (Android, Windows, macOS, ChromeOS): one-click native install.
// iPhone/iPad: Apple allows no programmatic install, so we show the two-tap Add to Home Screen steps.
// Desktop: a QR code opens the site on a phone, ready to install there.
(() => {
  const standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  if ("serviceWorker" in navigator && window.isSecureContext) {
    addEventListener("load", () => navigator.serviceWorker.register("/firebase-messaging-sw.js", { scope: "/" }).catch(() => {}));
  }
  const panel = document.getElementById("mfa-panel");
  const bar = document.getElementById("mfa-bar");
  const openers = [...document.querySelectorAll("[data-app-open]")];
  if (!panel) return;
  if (standalone) {                       // already running as the app: no install UI anywhere
    openers.forEach((b) => (b.hidden = true));
    if (bar) bar.remove();
    return;
  }
  const ua = navigator.userAgent;
  const ios = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const iosSafari = ios && /Safari\//.test(ua) && !/CriOS|FxiOS|EdgiOS|OPiOS/.test(ua);
  const android = /Android/.test(ua);
  const mobile = ios || android || matchMedia("(max-width: 760px) and (pointer: coarse)").matches;
  let deferred = null;
  const KEY = "mfa-dismissed";
  const dismissedRecently = () => { try { return Date.now() - (+localStorage.getItem(KEY) || 0) < 14 * 864e5; } catch { return false; } };

  const show = (name, on) => panel.querySelectorAll(`[data-a="${name}"]`).forEach((el) => (el.hidden = !on));
  function render() {
    show("native", !!deferred);
    show("ios", ios);
    show("ios-other", ios && !iosSafari);
    show("manual", !deferred && !ios && mobile);
    show("qr", !mobile);
    show("desktop-manual", !deferred && !mobile);
  }
  function open() { render(); panel.hidden = false; openers.forEach((b) => b.setAttribute("aria-expanded", "true")); panel.querySelector("h2").focus(); }
  function close(focusBack) { panel.hidden = true; openers.forEach((b) => b.setAttribute("aria-expanded", "false")); if (focusBack) focusBack.focus(); }
  async function install() {
    if (!deferred) return open();
    deferred.prompt();
    const { outcome } = await deferred.userChoice;
    deferred = null;
    if (outcome === "accepted") { close(); bar && bar.remove(); }
    else render();
  }

  addEventListener("beforeinstallprompt", (e) => {   // browser says the site is installable: take over the prompt
    e.preventDefault();
    deferred = e;
    render();
    maybeBar();
  });
  addEventListener("appinstalled", () => { deferred = null; openers.forEach((b) => (b.hidden = true)); bar && bar.remove(); close(); });

  openers.forEach((b) => b.addEventListener("click", () => (panel.hidden ? open() : close(b))));
  panel.querySelector(".mfa-x").addEventListener("click", () => close(openers.find((b) => b.offsetParent)));
  panel.querySelector('[data-act="install"]').addEventListener("click", install);
  panel.addEventListener("keydown", (e) => { if (e.key === "Escape") close(openers.find((b) => b.offsetParent)); });
  document.addEventListener("click", (e) => {
    if (!panel.hidden && !panel.contains(e.target) && !openers.some((b) => b.contains(e.target)) && !(bar && bar.contains(e.target))) close();
  });

  // phone install bar: only where installing is possible, never on the app itself, not again for 14 days once closed
  function maybeBar() {
    if (!bar || !mobile || dismissedRecently()) return;
    if (!(deferred || iosSafari)) return;
    bar.hidden = false;
  }
  if (bar) {
    bar.querySelector('[data-act="bar-install"]').addEventListener("click", () => (deferred ? install() : open()));
    bar.querySelector(".mfa-bar-x").addEventListener("click", () => { bar.hidden = true; try { localStorage.setItem(KEY, String(Date.now())); } catch {} });
    if (iosSafari) setTimeout(maybeBar, 1500);
  }
  if (new URLSearchParams(location.search).get("source") === "qr-app" && mobile) setTimeout(open, 600);  // arrived from the QR code
})();
