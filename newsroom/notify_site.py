"""Site build pieces for push alerts: bell + panel HTML, service worker, web app manifest, icons.

The bell only renders when newsroom/firebase-web.json is enabled and complete, so the site never
shows a control that can't work. The manifest and icons always ship (they also make "Add to Home
Screen" look right on phones).
"""
import json
from html import escape
from pathlib import Path

from notify_logic import DEFAULT_FREQ, DEFAULT_TOPICS, FREQUENCIES, TOPICS

HERE = Path(__file__).resolve().parent
CONFIG = HERE / "firebase-web.json"

BELL_SVG = ('<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false"><path d="M12 3a6 6 0 0 0-6 6v3.6l-1.6 2.7A1 1 0 0 0 5.3 17h13.4a1 1 0 0 0 .9-1.7L18 12.6V9a6 6 0 0 0-6-6Z" '
            'fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M9.5 19.5a2.5 2.5 0 0 0 5 0" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>')
SHARE_SVG = ('<svg viewBox="0 0 24 24" width="15" height="15" aria-label="Share" role="img"><path d="M12 3v12M8 7l4-4 4 4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
             '<path d="M6 11H5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-8a1 1 0 0 0-1-1h-1" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>')


def config():
    try:
        c = json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    fb = c.get("firebase") or {}
    if not c.get("enabled") or not c.get("vapidKey") or not all(fb.get(k) for k in ("apiKey", "authDomain", "projectId", "messagingSenderId", "appId")):
        return None
    return c


def bell():
    """Bell button + panel, placed in the masthead next to Follow. Empty when alerts are off."""
    c = config()
    if not c:
        return ""
    client = {"sdk": c["sdk"], "firebase": c["firebase"], "vapidKey": c["vapidKey"],
              "defaults": {"topics": DEFAULT_TOPICS, "freq": DEFAULT_FREQ}}
    freqs = "".join(f'<label class="mfn-opt"><input type="radio" name="freq" value="{v}"><span>{escape(lbl)}</span></label>' for v, lbl in FREQUENCIES)
    topics = "".join(f'<label class="mfn-opt"><input type="checkbox" name="topic" value="{v}"><span>{escape(lbl)}</span></label>' for v, lbl, _ in TOPICS)
    return f"""<button type="button" class="mfn-bell" id="mfn-bell" aria-label="News alerts: off" aria-haspopup="dialog" aria-expanded="false" aria-controls="mfn-panel">{BELL_SVG}<span class="mfn-dot" aria-hidden="true"></span></button>
<div class="mfn" id="mfn-panel" role="dialog" aria-modal="false" aria-labelledby="mfn-h" hidden>
  <div class="mfn-head"><div id="mfn-h" class="mfn-title" role="heading" aria-level="2" tabindex="-1">News alerts</div><button type="button" class="mfn-x" aria-label="Close">&times;</button></div>
  <p class="mfn-status" id="mfn-status" role="status" aria-live="polite"></p>
  <div data-v="unsupported" hidden><p>This browser can't receive web alerts. Chrome, Edge, Firefox and Safari can, on desktop and Android.</p></div>
  <div data-v="ios" hidden><p>On iPhone and iPad, alerts work once MetaFlora News is on your Home Screen:</p>
    <ol class="mfn-steps"><li>In Safari, tap Share {SHARE_SVG}</li><li>Choose <b>Add to Home Screen</b>, then <b>Add</b></li><li>Open MetaFlora News from your Home Screen and tap the bell</li></ol>
    <p class="mfn-note">Needs iOS or iPadOS 16.4 or later.</p></div>
  <div data-v="denied" hidden><p>Alerts are blocked for this site. Allow notifications for news.metaflora.xyz in your browser's site settings, then reload this page.</p></div>
  <form data-v="prefs" hidden>
    <fieldset><legend>How often</legend>{freqs}</fieldset>
    <fieldset class="mfn-topics"><legend>Topics</legend>{topics}</fieldset>
    <div class="mfn-actions">
      <button type="submit" class="mfn-primary" data-act="enable">Turn on alerts</button>
      <button type="button" class="mfn-primary" data-act="save" hidden>Save preferences</button>
      <button type="button" class="mfn-ghost" data-act="disable" hidden>Turn off alerts</button>
    </div>
    <p class="mfn-note">Free, no account. We keep an anonymous device ID, this browser's push address and your choices; no name or email. <a href="/how-we-report/#alerts">Privacy</a></p>
  </form>
</div>
<script type="application/json" id="mfn-push-config">{json.dumps(client)}</script>"""


def head_tags(css_version):
    """Manifest + icons in every page head; the alerts module only when alerts are on."""
    tags = ('<link rel="manifest" href="/manifest.webmanifest">'
            '<link rel="apple-touch-icon" href="/assets/icons/apple-touch-icon.png">'
            '<meta name="apple-mobile-web-app-capable" content="yes">'
            '<meta name="mobile-web-app-capable" content="yes">'
            '<meta name="apple-mobile-web-app-title" content="MetaFlora News">'
            '<meta name="apple-mobile-web-app-status-bar-style" content="black">')
    tags += f'<script src="/assets/app.js?v={css_version}" defer></script>'
    if config():
        tags += f'<script type="module" src="/assets/notify.js?v={css_version}"></script>'
    return tags


def write_static(out, write):
    """manifest.webmanifest, icons, and the service worker (only when alerts are on)."""
    from PIL import Image
    icons = out / "assets" / "icons"
    icons.mkdir(parents=True, exist_ok=True)
    cube = Image.open(HERE / "assets" / "metaflora-cube.png").convert("RGBA")
    for name, size, pad in (("icon-192.png", 192, 0.16), ("icon-512.png", 512, 0.16), ("maskable-512.png", 512, 0.26),
                            ("apple-touch-icon.png", 180, 0.14), ("badge-96.png", 96, 0.1)):
        p = icons / name
        if p.exists():
            continue
        bg = Image.new("RGBA", (size, size), (19, 19, 19, 255) if name != "badge-96.png" else (0, 0, 0, 0))
        h = round(size * (1 - 2 * pad))
        c = cube.resize((round(h * cube.width / cube.height), h), Image.LANCZOS)
        if name == "badge-96.png":  # monochrome silhouette for Android's status bar
            alpha = c.split()[3]
            c = Image.new("RGBA", c.size, (255, 255, 255, 255)); c.putalpha(alpha)
        bg.alpha_composite(c, ((size - c.width) // 2, (size - c.height) // 2))
        bg.save(p, optimize=True)
    manifest = {
        "name": "MetaFlora News", "short_name": "MetaFlora News", "id": "/", "start_url": "/?source=app", "scope": "/",
        "display": "standalone", "display_override": ["standalone", "minimal-ui"], "orientation": "any",
        "background_color": "#131313", "theme_color": "#131313", "lang": "en", "dir": "ltr",
        "categories": ["news", "business", "finance"],
        "description": "Cannabis industry news: policy, markets, science and the business of cannabis. Morning and evening editions.",
        "icons": [{"src": "/assets/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "/assets/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
                  {"src": "/assets/icons/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
        "shortcuts": [
            {"name": "Latest news", "short_name": "Latest", "url": "/?source=app-shortcut", "icons": [{"src": "/assets/icons/icon-192.png", "sizes": "192x192"}]},
            {"name": "Cannabis stocks", "short_name": "Stocks", "url": "/stocks/?source=app-shortcut", "icons": [{"src": "/assets/icons/icon-192.png", "sizes": "192x192"}]},
            {"name": "Markets news", "short_name": "Markets", "url": "/section/markets/?source=app-shortcut", "icons": [{"src": "/assets/icons/icon-192.png", "sizes": "192x192"}]},
        ],
        "prefer_related_applications": False,
    }
    write("manifest.webmanifest", json.dumps(manifest, indent=1))
    ico = out / "favicon.ico"  # apps (WhatsApp included) often look for /favicon.ico first
    Image.open(icons / "icon-192.png").convert("RGBA").save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    write("offline/index.html", OFFLINE_HTML)
    # One service worker for the app (offline page) and for alerts. Registered on every page by app.js.
    write("firebase-messaging-sw.js", SW_JS)


OFFLINE_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>Offline · MetaFlora News</title><meta name="theme-color" content="#131313">
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#131313;color:#e6e6e6;font:17px/1.5 Georgia,serif;text-align:center;padding:24px}
img{width:64px;height:auto;margin:0 auto 18px;display:block}h1{font-size:26px;color:#f2f2f2;margin:0 0 8px;font-weight:500}p{margin:0 0 20px;color:#c9c9c9}
button{font:700 15px Helvetica,Arial,sans-serif;background:#a3e635;color:#0d0d0d;border:0;border-radius:4px;padding:11px 18px;cursor:pointer}</style></head>
<body><main><img src="/assets/icons/icon-192.png" alt="" width="64" height="64"><h1>You're offline</h1>
<p>MetaFlora News needs a connection to load the latest stories.</p><button onclick="location.reload()">Try again</button></main></body></html>
"""

SW_JS = """// MetaFlora News service worker: the installable app (offline page) and news alerts.
// Network-first for pages with a small offline fallback; nothing else is cached, so readers always get fresh news.
// Alerts are displayed here directly (Firebase's own worker hands them to an open tab, which would swallow them).
const SHELL = "mfn-shell-v2";
const OFFLINE = "/offline/";
const ORIGIN = self.location.origin;

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll([OFFLINE, "/assets/icons/icon-192.png"])).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(Promise.all([
    // navigation preload: the page request starts while the worker boots, so a returning reader never waits on it
    self.registration.navigationPreload ? self.registration.navigationPreload.enable().catch(() => {}) : null,
    caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== SHELL).map((k) => caches.delete(k)))),
  ]).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const r = e.request;
  if (r.mode !== "navigate" || r.method !== "GET") return;   // only page loads; assets go straight to the network
  e.respondWith((async () => {
    try {
      const pre = await e.preloadResponse;   // undefined when preload is off or unsupported
      return pre || await fetch(r);
    } catch (_) {
      return caches.match(OFFLINE);
    }
  })());
});

self.addEventListener("push", (event) => {
  let p = {};
  try { p = event.data ? event.data.json() : {}; } catch (e) {}
  const n = p.notification || {};
  const d = p.data || {};
  const link = d.link || (p.fcmOptions && p.fcmOptions.link) || "/";
  event.waitUntil(self.registration.showNotification(n.title || d.title || "MetaFlora News", {
    body: n.body || d.body || "",
    icon: n.icon || "/assets/icons/icon-192.png",
    badge: n.badge || "/assets/icons/badge-96.png",
    image: n.image || undefined,
    tag: n.tag || d.key || undefined,
    renotify: false,
    actions: (n.actions || []).slice(0, 2),
    data: { link },
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const link = event.action === "settings" ? ORIGIN + "/?alerts=settings" : ((event.notification.data && event.notification.data.link) || "/");
  event.waitUntil((async () => {
    const wins = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const w of wins) {
      if (w.url.split("?")[0] === link.split("?")[0] && "focus" in w) return w.focus();
    }
    return self.clients.openWindow(link);
  })());
});
"""


PHONE_SVG = ('<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false"><rect x="6.5" y="2.5" width="11" height="19" rx="2.2" fill="none" stroke="currentColor" stroke-width="1.7"/>'
             '<path d="M10.5 18.5h3" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>')


def app_button():
    """Masthead "Get the app" button (desktop; phones get the install bar and the footer link)."""
    return (f'<button type="button" class="mfa-btn" data-app-open aria-haspopup="dialog" aria-expanded="false" aria-controls="mfa-panel">'
            f'{PHONE_SVG}<span>Get the app</span></button>')


def app_ui():
    """Install panel + phone install bar, once per page (placed before </body>)."""
    return f"""<div class="mfa" id="mfa-panel" role="dialog" aria-modal="false" aria-labelledby="mfa-h" hidden>
  <div class="mfn-head"><h2 id="mfa-h" tabindex="-1">Get the MetaFlora News app</h2><button type="button" class="mfa-x mfn-x" aria-label="Close">&times;</button></div>
  <p class="mfa-lede">Free, no app store, no account. Opens full screen from your home screen or dock, with optional news alerts.</p>
  <div data-a="native" hidden><button type="button" class="mfn-primary mfa-install" data-act="install">{PHONE_SVG}<span>Install MetaFlora News</span></button></div>
  <div data-a="ios" hidden><p>On iPhone and iPad, add it in two taps:</p>
    <ol class="mfn-steps"><li>Tap Share {SHARE_SVG} in Safari's toolbar</li><li>Choose <b>Add to Home Screen</b>, then <b>Add</b></li></ol>
    <p class="mfn-note" data-a="ios-other" hidden>Open this page in Safari first: other browsers on iPhone can't add web apps.</p></div>
  <div data-a="manual" hidden><p>Open your browser's menu (&#8942;) and choose <b>Install app</b> or <b>Add to Home screen</b>.</p></div>
  <div data-a="qr" hidden><div class="mfa-qr"><img src="/assets/app-qr.svg" alt="QR code that opens news.metaflora.xyz on your phone" width="174" height="174">
    <p><b>On your phone</b>Scan with your camera to open MetaFlora News, then tap <b>Install</b> (Android) or <b>Share › Add to Home Screen</b> (iPhone).</p></div></div>
  <div data-a="desktop-manual" hidden><p class="mfn-note">To install on this computer, use Chrome or Edge (install icon in the address bar), or in Safari choose <b>File › Add to Dock</b>.</p></div>
</div>
<div class="mfa-bar" id="mfa-bar" role="region" aria-label="Get the app" hidden>
  <img src="/assets/icons/icon-192.png" alt="" width="40" height="40">
  <p><b>MetaFlora News app</b><span>Free · no app store · news alerts</span></p>
  <button type="button" class="mfn-primary" data-act="bar-install">Install</button>
  <button type="button" class="mfa-bar-x" aria-label="Not now">&times;</button>
</div>"""
