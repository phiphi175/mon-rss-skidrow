"use strict";

const list = document.querySelector("#articles");
const search = document.querySelector("#search");
const count = document.querySelector("#item-count");
const checked = document.querySelector("#checked-at");
const status = document.querySelector("#feed-status");
const notice = document.querySelector("#notice");
const shown = document.querySelector("#shown-count");
const items = [];

function dateLabel(value) {
  if (!value) return "Date de publication inconnue";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date de publication inconnue";
  return new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric", timeZone: "Europe/Paris" }).format(date);
}
function timeLabel(value) {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return "—";
  return new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Paris" }).format(dt);
}
function appendArticle(item) {
  // Pas de HTML provenant du site source : injection évitée avec textContent.
  const row = document.createElement("a");
  row.className = "article";
  row.href = item.url;
  row.target = "_blank";
  row.rel = "noopener noreferrer";
  // La miniature est chargée directement sur son hébergeur d'origine ;
  // en cas de blocage (hotlink/403), la carte reste utilisable sans image.
  if (item.image) {
    try {
      const imgUrl = new URL(item.image);
      if (imgUrl.protocol === "https:" && /\.(?:jpe?g|png|webp|gif|avif)$/i.test(imgUrl.pathname)) {
        const img = document.createElement("img");
        img.className = "article-image";
        img.src = imgUrl.href;
        img.alt = "";
        img.loading = "lazy";
        img.decoding = "async";
        img.referrerPolicy = "no-referrer";
        img.addEventListener("error", () => img.remove());
        row.append(img);
      }
    } catch { /* miniature absente ou URL invalide */ }
  }
  const main = document.createElement("div");
  main.className = "article-main";
  const title = document.createElement("h3");
  title.className = "article-title";
  title.textContent = item.title;
  const meta = document.createElement("div");
  meta.className = "article-meta";
  const badge = document.createElement("span");
  badge.className = "article-tag";
  badge.textContent = "PUBLICATION";
  const date = document.createElement("span");
  date.textContent = dateLabel(item.published);
  const arrow = document.createElement("span");
  arrow.className = "article-arrow";
  arrow.textContent = "↗";
  arrow.setAttribute("aria-hidden", "true");
  meta.append(badge, date);
  main.append(title, meta);
  row.append(main, arrow);
  list.append(row);
}
function render() {
  const filter = search.value.trim().toLocaleLowerCase("fr-FR");
  const results = items.filter(item => item.title.toLocaleLowerCase("fr-FR").includes(filter));
  list.replaceChildren();
  if (results.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = items.length ? "Aucun résultat pour cette recherche." : "Aucune publication disponible pour le moment. Consulte le statut du flux ci-dessus.";
    list.append(empty);
  } else {
    results.forEach(appendArticle);
  }
  shown.textContent = `${results.length} publication${results.length > 1 ? "s" : ""} affichée${results.length > 1 ? "s" : ""}`;
}
async function load() {
  try {
    const response = await fetch("./items.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    for (const item of data.items || []) {
      try {
        const link = new URL(item.url);
        if (!["https:"].includes(link.protocol)) continue;
        if (link.hostname !== "www.skidrowreloaded.com" && link.hostname !== "skidrowreloaded.com") continue;
        items.push(item);
      } catch { /* lien non exploitable */ }
    }
    count.textContent = String(items.length);
    checked.textContent = timeLabel(data.checked_at);
    const ok = data.status === "ok";
    const demo = data.status === "demo";
    status.className = `status ${ok ? "ok" : "error"}`;
    status.replaceChildren();
    const dot = document.createElement("span");
    dot.className = "status-dot";
    dot.setAttribute("aria-hidden", "true");
    status.append(dot, document.createTextNode(ok ? "À jour" : demo ? "Démonstration" : "Source inaccessible"));
    if (!ok) {
      notice.hidden = false;
      notice.textContent = demo ? "Les deux publications présentées sont fictives : lance une vraie mise à jour pour récupérer le site source." :
        "Impossible de récupérer les nouvelles publications pour le moment. Les anciennes entrées sont conservées. Vérifie les journaux dans GitHub → Actions ; la source peut refuser les robots (403).";
      if (demo) notice.classList.add("info");
    } else {
      notice.hidden = true;
    }
    render();
  } catch (err) {
    status.textContent = "Erreur d'affichage";
    count.textContent = "0";
    checked.textContent = "—";
    notice.hidden = false;
    notice.textContent = "Impossible de lire les données du site. Vérifie la publication GitHub Pages.";
    list.innerHTML = '<div class="empty">Aucune donnée lisible.</div>';
  }
}
search.addEventListener("input", render);
document.querySelector("#copy-feed").addEventListener("click", async (event) => {
  const link = new URL("./feed.xml", window.location.href).href;
  try {
    await navigator.clipboard.writeText(link);
    event.currentTarget.textContent = "Adresse copiée ✓";
    setTimeout(() => { event.currentTarget.textContent = "Copier l'adresse du RSS ⧉"; }, 2000);
  } catch {
    window.prompt("Copie cette adresse RSS :", link);
  }
});
load();
