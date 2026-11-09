// MetaFlora News alerts dashboard. Read-only: Firestore rules let only admins/{uid} accounts read.
// Uses a separate Firebase app instance ("admin") so signing in with Google here never replaces the
// anonymous identity this browser uses for its own alert subscription.
const CFG = JSON.parse(document.getElementById("adm-config").textContent);
const SDK = `https://www.gstatic.com/firebasejs/${CFG.sdk}`;
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const [appM, authM, fsM] = await Promise.all([
  import(`${SDK}/firebase-app.js`), import(`${SDK}/firebase-auth.js`), import(`${SDK}/firebase-firestore.js`)]);
const app = appM.initializeApp(CFG.firebase, "admin");
const auth = authM.getAuth(app);
const db = fsM.getFirestore(app);

// this browser's anonymous reader identity (exists only if alerts were turned on here)
const readerApp = appM.getApps().find((a) => a.name === "[DEFAULT]") || appM.initializeApp(CFG.firebase);
const readerAuth = authM.getAuth(readerApp);
const readerUid = await new Promise((res) => { const off = authM.onAuthStateChanged(readerAuth, (u) => { off(); res(u && u.isAnonymous ? u.uid : null); }); });

$("adm-signin").addEventListener("click", async () => {
  if (auth.currentUser) return authM.signOut(auth);
  try { await authM.signInWithPopup(auth, new authM.GoogleAuthProvider()); } catch (e) { $("adm-who").textContent = `Sign-in failed: ${e.code || e.message}`; }
});
authM.onAuthStateChanged(auth, async (user) => {
  $("adm-signin").textContent = user ? "Sign out" : "Sign in with Google";
  $("adm-body").hidden = true;
  if (!user) { $("adm-who").textContent = "Sign in with the Google account listed as an admin."; return; }
  const me = await fsM.getDoc(fsM.doc(db, "admins", user.uid)).catch(() => null);
  if (!me || !me.exists()) {
    $("adm-who").innerHTML = `Signed in as ${esc(user.email)}, which is not an admin yet. In the Firebase console, add a document
      <code>admins/${esc(user.uid)}</code> to Firestore (any fields), then reload.`;
    return;
  }
  $("adm-who").textContent = `Signed in as ${user.email}.`;
  $("adm-body").hidden = false;
  try { await load(user, me.data()); } catch (e) { $("adm-kpis").textContent = `Could not load: ${e.code || e.message}`; console.warn(e); }
});

async function load(user, me) {
  const [devSnap, sendSnap, clickSnap] = await Promise.all([
    fsM.getDocs(fsM.collection(db, "devices")),
    fsM.getDocs(fsM.query(fsM.collection(db, "sends"), fsM.orderBy("created", "desc"), fsM.limit(40))),
    fsM.getDocs(fsM.collection(db, "clicks")),
  ]);
  const devs = devSnap.docs.map((d) => d.data());
  const on = devs.filter((d) => d.enabled);
  const sends = sendSnap.docs.map((d) => ({ id: d.id, ...d.data() }));
  const clicks = {};
  clickSnap.docs.forEach((d) => { const k = d.data().key; clicks[k] = (clicks[k] || 0) + 1; });
  const live = sends.filter((s) => s.live);
  const sent = live.reduce((n, s) => n + (s.sent || 0), 0);
  const failed = live.reduce((n, s) => n + (s.failed || 0), 0);
  const totalClicks = Object.values(clicks).reduce((a, b) => a + b, 0);
  const kpi = (k, v, sub = "") => `<div><dt>${k}</dt><dd>${v}</dd>${sub ? `<p>${sub}</p>` : ""}</div>`;
  $("adm-kpis").innerHTML = `<dl class="stk-stats adm-kpi">${[
    kpi("Active devices", on.length, "One per browser. Readers are anonymous, so devices ≈ subscribers."),
    kpi("Alerts delivered", sent, `${live.length} live sends`),
    kpi("Failed", failed, sent + failed ? `${((failed / (sent + failed)) * 100).toFixed(1)}%` : ""),
    kpi("Clicks", totalClicks, sent ? `${((totalClicks / sent) * 100).toFixed(1)}% click-through` : ""),
  ].join("")}</dl>`;
  const bars = (rows) => `<ul class="adm-bars">${rows.map(([lbl, n]) => `<li><span>${esc(lbl)}</span><b>${n}</b><i style="width:${on.length ? (n / on.length) * 100 : 0}%"></i></li>`).join("")}</ul>`;
  $("adm-freq").innerHTML = bars(CFG.freqs.map(([id, lbl]) => [lbl, on.filter((d) => d.freq === id).length]));
  $("adm-topics").innerHTML = bars(CFG.topics.map(([id, lbl]) => [lbl, on.filter((d) => (d.topics || []).includes(id)).length]));
  // growth
  const days = [...Array(30)].map((_, i) => { const d = new Date(Date.now() - (29 - i) * 864e5); return d.toISOString().slice(0, 10); });
  const per = Object.fromEntries(days.map((d) => [d, 0]));
  devs.forEach((d) => { const t = d.created?.toDate?.(); if (t) { const k = t.toISOString().slice(0, 10); if (k in per) per[k]++; } });
  const max = Math.max(1, ...Object.values(per));
  $("adm-growth").innerHTML = days.map((d) => `<span title="${d}: ${per[d]}" style="height:${(per[d] / max) * 100}%"></span>`).join("");
  // sends
  $("adm-sends").innerHTML = `<thead><tr><th scope="col">Alert</th><th scope="col">Kind</th><th scope="col">Audience</th><th scope="col">Sent</th><th scope="col">Failed</th><th scope="col">Clicks</th><th scope="col">Status</th></tr></thead><tbody>${
    sends.map((s) => `<tr><th scope="row">${esc(s.title || s.id)}<span class="tk">${esc(s.id)}</span></th><td>${esc(s.kind)}${s.manual ? " · manual" : ""}</td>
      <td>${s.audience ?? ""}</td><td>${s.sent ?? ""}</td><td>${s.failed ?? ""}</td><td>${clicks[s.id] || 0}</td><td>${esc(s.status)}${s.live ? "" : " (dry run)"}</td></tr>`).join("")
    || '<tr><td colspan="7">No alerts sent yet.</td></tr>'}</tbody>`;
  // test devices
  const mine = me.devices || [];
  $("adm-devices").innerHTML = `<p class="mfn-note">Test sends go only to devices listed here. ${readerUid ? `This browser's device ID is <code>${esc(readerUid)}</code>.` : "Turn on alerts with the bell in this browser first, then register it here."}</p>
    <ul class="adm-devlist">${mine.map((id) => `<li><code>${esc(id)}</code>${id === readerUid ? " (this browser)" : ""}</li>`).join("") || "<li>None yet.</li>"}</ul>
    ${readerUid && !mine.includes(readerUid) ? '<button type="button" class="mfn-primary" id="adm-reg">Register this browser as a test device</button>' : ""}`;
  $("adm-reg")?.addEventListener("click", async () => {
    await fsM.updateDoc(fsM.doc(db, "admins", user.uid), { devices: fsM.arrayUnion(readerUid) });
    load(user, { ...me, devices: [...mine, readerUid] });
  });
}

// Ready for X: one-tap compose links for the latest edition's top stories ("posted" is remembered on this device)
{
  const KEY = "mfn-x-posted";
  const done = (() => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; } })();
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(done)); } catch {} };
  const list = $("adm-xlist");
  const draw = () => {
    list.innerHTML = (CFG.xready || []).map((x) => `<li class="${done[x.key] ? "is-done" : ""}">
      <p class="adm-xmeta">${esc(x.edition)} · ${x.label ? esc(x.label) : "rank " + x.rank}${done[x.key] ? " · <b>posted</b>" : ""}</p>
      <p class="adm-xtext">${esc(x.text)}</p>
      ${x.image ? `<a class="adm-xcard" href="${esc(x.image)}" target="_blank" rel="noopener" title="The image card X shows under this post (opens full size)">
        <img src="${esc(x.image)}?v=${esc(CFG.built || "")}" alt="${esc(x.image_alt || "")}" width="1200" height="630" loading="lazy">
        <span>${esc(x.url.replace(/^https?:\/\//, "").split("/")[0])}</span></a>` : ""}
      <p class="adm-xurl">${esc(x.url)}</p>
      <p class="adm-xbtns"><a class="mfn-primary" href="${esc(x.intent)}" target="_blank" rel="noopener" data-k="${esc(x.key)}">Post on X</a>
      ${x.id ? `<a class="mfn-ghost" href="${esc(CFG.discord)}" target="_blank" rel="noopener" data-discord="${esc(x.id)}" title="Copies the story id, then opens the Discord workflow: Run workflow, paste, Run">Post to Discord</a>` : ""}
      <button type="button" class="mfn-ghost" data-mark="${esc(x.key)}">${done[x.key] ? "Undo" : "Mark posted"}</button></p></li>`).join("")
      || "<li>No stories yet.</li>";
  };
  list.addEventListener("click", (e) => {
    const dc = e.target.closest("[data-discord]");
    if (dc) { try { navigator.clipboard.writeText(dc.dataset.discord); } catch {} dc.textContent = "Id copied: paste it in Run workflow"; return; }
    const m = e.target.closest("[data-mark]");
    if (m) { const k = m.dataset.mark; if (done[k]) delete done[k]; else done[k] = Date.now(); save(); draw(); }
  });
  draw();
}

// preview: what readers would see for a recent story (built from the real headline and dek)
const pick = $("adm-article");
pick.innerHTML = CFG.recent.map((a, i) => `<option value="${i}">${esc(a.key)}${a.breaking ? " · BREAKING" : ""}${a.push === false ? " · alerts off" : ""}</option>`).join("");
function preview() {
  const a = CFG.recent[+pick.value];
  if (!a) return;
  const topic = (CFG.topics.find(([id]) => id === a.topic) || [, "—"])[1];
  $("adm-preview").innerHTML = `<div class="adm-note"><img src="/assets/icons/icon-192.png" alt="" width="40" height="40">
    <div><p class="adm-app">MetaFlora News · news.metaflora.xyz</p><p class="adm-title">${esc(a.title)}</p><p class="adm-body">${esc(a.body)}</p></div></div>
    <dl class="adm-meta"><div><dt>Opens</dt><dd><a href="${esc(a.link)}" target="_blank" rel="noopener">${esc(a.link.split("?")[0])}</a></dd></div>
    <div><dt>Goes to</dt><dd>${a.breaking ? "Breaking-news subscribers, plus " : ""}"every story" subscribers following ${esc(topic)}</dd></div>
    <div><dt>Article key</dt><dd><code>${esc(a.key)}</code> (type this to confirm a manual send)</dd></div></dl>`;
}
pick.addEventListener("change", preview);
preview();
