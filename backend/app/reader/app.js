const SAVED_KEY = "ghanaed.saved.v1";
const PINNED_KEY = "ghanaed.categories.v1";
const VISIT_KEY = "ghanaed.visit.v1";
const SEEN_KEY = "ghanaed.seen.v1";
const PAGE_SIZE = 20;
let seenCutoff = null;

const CATEGORY_LABELS = {
  teachers: "Teachers",
  higher_education: "University",
  basic_schools: "Basic schools",
  examinations: "Examinations",
  scholarships: "Scholarships",
  policy: "Policy",
  general: "General",
};

const STATIC = document.documentElement.dataset.feed === "static";
let catalog = null;

const main = document.querySelector("#main");
const categoriesEl = document.querySelector("#categories");
const searchForm = document.querySelector("#search");
const searchInput = document.querySelector("#search-input");
let categoriesExpanded = false;

let categoryNames = [];

function label(category) {
  if (!category) return "All";
  return CATEGORY_LABELS[category] || category.replaceAll("_", " ");
}

function savedStories() {
  try {
    const parsed = JSON.parse(localStorage.getItem(SAVED_KEY) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeSaved(stories) {
  localStorage.setItem(SAVED_KEY, JSON.stringify(stories));
}

function isSaved(id) {
  return savedStories().some((story) => story.id === id);
}

function toggleSaved(story) {
  const current = savedStories();
  if (current.some((item) => item.id === story.id)) {
    writeSaved(current.filter((item) => item.id !== story.id));
    return false;
  }
  const copy = {
    id: story.id,
    title: story.title,
    summary: story.summary,
    category: story.category,
    published_at: story.published_at,
    source_count: story.source_count,
    sources: story.sources || [],
    image_url: story.image_url || null,
    path: story.path || "",
    articles: (story.articles || []).map((article) => ({
      source_name: article.source_name,
      title: article.title,
      url: article.url,
      published_at: article.published_at,
      excerpt: article.excerpt,
    })),
  };
  writeSaved([copy, ...current]);
  return true;
}

function route() {
  const raw = decodeURIComponent((location.hash || "#/").slice(1));
  const parts = raw.split("/").filter(Boolean);
  if (parts[0] === "saved") return { name: "saved" };
  if (parts[0] === "story") return { name: "story", id: Number(parts[1]) };
  if (parts[0] === "category") return { name: "latest", category: parts[1] || "" };
  if (parts[0] === "search") return { name: "latest", q: parts.slice(1).join("/") };
  return { name: "latest" };
}

function formatWhen(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

const SOURCE_DOMAINS = {
  "3News": "3news.com",
  "Adom Online Education": "adomonline.com",
  "Edulens360": "edulens360.com",
  "Ghana Tertiary Education Commission": "gtec.edu.gh",
  "MyJoyOnline Education": "myjoyonline.com",
};

function isOriginalTip(story) {
  const names = sourceNames(story);
  return names.length === 1 && names[0] === "Edulens360";
}

function tipLead(excerpt, limit = 280) {
  let text = String(excerpt || "").replace(/\r\n/g, "\n");
  const marker = "### Related Edulens360 tips";
  if (text.includes(marker)) text = text.split(marker)[0];
  const chunks = text
    .split(/\n\n+/)
    .map((part) => part.trim())
    .filter((part) => part && !part.startsWith("### "));
  let lead = (chunks[0] || text.trim()).replace(/\s+/g, " ").trim();
  if (lead.length <= limit) return lead;
  const trimmed = lead.slice(0, limit - 1).replace(/\s+\S*$/, "");
  return `${(trimmed || lead.slice(0, limit - 1)).replace(/\s+$/, "")}…`;
}

function sourceNames(story) {
  if (Array.isArray(story.sources) && story.sources.length) return story.sources;
  const names = [];
  for (const article of story.articles || []) {
    if (article.source_name && !names.includes(article.source_name)) names.push(article.source_name);
  }
  return names;
}

function sourceInitials(name) {
  const words = name.replace(/[^A-Za-z0-9 ]/g, " ").split(/\s+/).filter(Boolean);
  const skip = new Set(["of", "the", "and", "online", "education"]);
  const picked = words.filter((word) => !skip.has(word.toLowerCase()));
  return (picked.length ? picked : words).slice(0, 2).map((word) => word[0].toUpperCase()).join("");
}

function sourceMark(name) {
  const mark = el("span", "source-mark");
  mark.title = name;
  mark.setAttribute("aria-label", name);
  const domain = SOURCE_DOMAINS[name];
  if (!domain) {
    mark.textContent = sourceInitials(name);
    return mark;
  }
  const img = document.createElement("img");
  img.alt = "";
  img.src = `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=64`;
  img.addEventListener("error", () => {
    img.remove();
    mark.textContent = sourceInitials(name);
  });
  mark.append(img);
  return mark;
}

function sourceLabel(count) {
  return count === 1 ? "1 source" : `${count} sources`;
}

function cardMeta(story) {
  const row = el("p", "meta");
  const names = sourceNames(story);
  row.append(el("span", "", isOriginalTip(story) ? "Edulens360 tip" : sourceLabel(story.source_count)));
  if (!names.length) return row;
  const marks = el("span", "source-marks");
  for (const name of names) marks.append(sourceMark(name));
  row.append(marks);
  return row;
}

function searchTerms(query) {
  return (query.toLowerCase().match(/[a-z0-9]+/g) || []).filter((term) => term.length >= 2);
}

function matchesStory(story, terms) {
  const haystack = [
    story.title,
    story.summary,
    ...(story.articles || []).flatMap((article) => [article.title, article.excerpt || ""]),
  ]
    .join(" ")
    .toLowerCase();
  return terms.every((term) => new RegExp(`\\b${term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`).test(haystack));
}

function filterStories(current) {
  if (!catalog) throw new Error("The feed could not be loaded.");
  let stories = catalog.stories || [];
  if (current.category) stories = stories.filter((story) => story.category === current.category);
  if (current.q) {
    const terms = searchTerms(current.q);
    stories = terms.length ? stories.filter((story) => matchesStory(story, terms)) : [];
  }
  return stories;
}

function staticStories(current, offset) {
  return filterStories(current).slice(offset, offset + PAGE_SIZE);
}

function readSeenAt() {
  const raw = localStorage.getItem(SEEN_KEY);
  if (!raw) return null;
  const when = Date.parse(raw);
  return Number.isNaN(when) ? null : when;
}

function rememberVisit() {
  localStorage.setItem(SEEN_KEY, new Date().toISOString());
}

function storyIsNew(story) {
  if (seenCutoff == null) return false;
  const when = Date.parse(story.published_at || "");
  return !Number.isNaN(when) && when > seenCutoff;
}

function newCountFor(current, pageStories) {
  if (STATIC) {
    try {
      return filterStories(current).filter(storyIsNew).length;
    } catch {
      return 0;
    }
  }
  return (pageStories || []).filter(storyIsNew).length;
}

function updatedHeading(current, pageStories) {
  const parts = [];
  if (STATIC && catalog && catalog.generated_at) {
    const date = new Date(catalog.generated_at);
    if (!Number.isNaN(date.getTime())) {
      const when = date.toLocaleString(undefined, {
        day: "numeric",
        month: "short",
        hour: "numeric",
        minute: "2-digit",
      });
      parts.push(`Latest update ${when}`);
    }
  }
  if (!current.q) {
    const fresh = newCountFor(current, pageStories);
    if (fresh > 0) parts.push(fresh === 1 ? "1 new" : `${fresh} new`);
  }
  return parts.join(" · ");
}

function storyShareUrl(story) {
  if (story.path) {
    const path = String(story.path).replace(/^\/+/, "");
    return `https://edulens360.com/${path}`;
  }
  return `https://edulens360.com/#/story/${story.id}`;
}

async function shareStory(story) {
  const url = storyShareUrl(story);
  const payload = {
    title: story.title || "Edulens360",
    text: story.summary || story.title || "Edulens360",
    url,
  };
  if (window.EdulensShare && typeof window.EdulensShare.share === "function") {
    try {
      window.EdulensShare.share(payload.title, payload.text, url);
      return "shared";
    } catch {
      // Fall through to browser share / copy.
    }
  }
  if (typeof navigator.share === "function") {
    try {
      if (!navigator.canShare || navigator.canShare(payload)) {
        await navigator.share(payload);
        return "shared";
      }
    } catch (error) {
      if (error && error.name === "AbortError") return "cancelled";
    }
  }
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(url);
      return "copied";
    }
  } catch {
    // Fall through to the prompt copy path.
  }
  try {
    window.prompt("Copy this Edulens360 link:", url);
    return "copied";
  } catch {
    return "failed";
  }
}

function flashShareFeedback(host, message) {
  if (!host) return;
  host.querySelectorAll(".share-toast").forEach((node) => node.remove());
  const tip = el("span", "share-toast", message);
  host.append(tip);
  window.setTimeout(() => tip.remove(), 1800);
}

function shareIcon() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", "14");
  svg.setAttribute("height", "14");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute(
    "d",
    "M14 4h6v6M20 4l-9 9M10 5H7a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3",
  );
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", "1.8");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  svg.append(path);
  return svg;
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    const error = new Error("The feed could not be loaded.");
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function clear(node) {
  node.replaceChildren();
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function pinnedCategories() {
  try {
    const parsed = JSON.parse(localStorage.getItem(PINNED_KEY) || "[]");
    return Array.isArray(parsed) ? parsed.filter((name) => typeof name === "string" && name) : [];
  } catch {
    return [];
  }
}

function pinCategory(name) {
  if (!name || pinnedCategories().includes(name)) return;
  localStorage.setItem(PINNED_KEY, JSON.stringify([...pinnedCategories(), name]));
}

function unpinCategory(name) {
  localStorage.setItem(PINNED_KEY, JSON.stringify(pinnedCategories().filter((item) => item !== name)));
}

let removeMenu = null;

function closeRemoveMenu() {
  if (!removeMenu) return;
  removeMenu.remove();
  removeMenu = null;
}

function showRemoveMenu(anchor, name) {
  closeRemoveMenu();
  const menu = el("div", "category-menu");
  const button = el("button", "", "Remove");
  button.type = "button";
  button.addEventListener("click", (event) => {
    event.preventDefault();
    unpinCategory(name);
    closeRemoveMenu();
    if (route().category === name) {
      location.hash = "#/";
      return;
    }
    renderCategories(route().category || "");
  });
  menu.append(button);
  categoriesEl.append(menu);
  const host = categoriesEl.getBoundingClientRect();
  const box = anchor.getBoundingClientRect();
  const width = menu.offsetWidth;
  const left = Math.min(Math.max(0, box.left - host.left), Math.max(0, host.width - width));
  menu.style.left = `${left}px`;
  menu.style.top = `${box.bottom - host.top + 6}px`;
  removeMenu = menu;
}

function holdToRemove(link, name) {
  let timer = 0;
  let held = false;
  let startX = 0;
  let startY = 0;
  const cancel = () => window.clearTimeout(timer);
  link.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    held = false;
    startX = event.clientX;
    startY = event.clientY;
    cancel();
    timer = window.setTimeout(() => {
      held = true;
      showRemoveMenu(link, name);
    }, 500);
  });
  link.addEventListener("pointermove", (event) => {
    if (Math.hypot(event.clientX - startX, event.clientY - startY) > 10) cancel();
  });
  link.addEventListener("pointerup", cancel);
  link.addEventListener("pointercancel", cancel);
  link.addEventListener("click", (event) => {
    if (!held) return;
    event.preventDefault();
    held = false;
  });
  link.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    showRemoveMenu(link, name);
  });
}

document.addEventListener("pointerdown", (event) => {
  if (removeMenu && !removeMenu.contains(event.target)) closeRemoveMenu();
});

function visibleCategories() {
  const known = new Set(categoryNames);
  return pinnedCategories().filter((name) => !known.size || known.has(name));
}

function categoryLink(name, active, pinned) {
  const link = el("a", "", label(name));
  link.href = `#/category/${encodeURIComponent(name)}`;
  if (name === active) link.setAttribute("aria-current", "true");
  if (pinned) holdToRemove(link, name);
  return link;
}

function renderCategories(active) {
  closeRemoveMenu();
  clear(categoriesEl);
  categoriesEl.hidden = false;
  const current = route();
  const onStory = current.name === "story";
  if (onStory) categoriesExpanded = false;

  const bar = el("div", "cat-bar");
  const latest = el("a", "", "Latest");
  latest.href = "#/";
  if (current.name === "latest" && !active) latest.setAttribute("aria-current", "true");
  const toggle = el("button", "categories-toggle", "Categories");
  toggle.type = "button";
  toggle.setAttribute("aria-expanded", categoriesExpanded ? "true" : "false");
  toggle.setAttribute("aria-controls", "category-list");
  toggle.addEventListener("click", () => {
    categoriesExpanded = !categoriesExpanded;
    renderCategories(active);
  });
  const saved = el("a", "", "Saved");
  saved.href = "#/saved";
  if (current.name === "saved") saved.setAttribute("aria-current", "true");
  bar.append(latest, toggle);
  for (const name of visibleCategories()) bar.append(categoryLink(name, active, true));
  bar.append(saved);
  categoriesEl.append(bar);

  if (!categoriesExpanded || onStory) return;
  const hidden = categoryNames.filter((name) => !visibleCategories().includes(name));
  if (!hidden.length) return;
  const list = el("div", "category-list");
  list.id = "category-list";
  for (const name of hidden) list.append(categoryLink(name, active));
  categoriesEl.append(list);
}

function bookmarkIcon() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", "14");
  svg.setAttribute("height", "14");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", "M6.5 3.5h11a1 1 0 0 1 1 1V20.5l-6.5-3.4-6.5 3.4V4.5a1 1 0 0 1 1-1z");
  svg.append(path);
  return svg;
}

function paintSave(button, on) {
  button.classList.toggle("saved", on);
  button.setAttribute("aria-pressed", on ? "true" : "false");
  button.setAttribute("aria-label", on ? "Remove save" : "Save");
}

function storyImage(story) {
  const direct = typeof story.image_url === "string" ? story.image_url.trim() : "";
  if (direct.startsWith("http://") || direct.startsWith("https://")) return direct;
  for (const article of story.articles || []) {
    const url = typeof article.image_url === "string" ? article.image_url.trim() : "";
    if (url.startsWith("http://") || url.startsWith("https://")) return url;
  }
  return "";
}

function headline(story) {
  const title = el("h2", "", story.title);
  const src = storyImage(story);
  if (!src) return title;
  const row = el("div", "headline");
  const img = document.createElement("img");
  img.className = "card-photo";
  img.alt = "";
  img.referrerPolicy = "no-referrer";
  try {
    img.src = new URL(src).href;
  } catch {
    img.src = src;
  }
  img.addEventListener("error", () => {
    row.replaceWith(title);
  });
  row.append(title, img);
  return row;
}

function storyHref(story) {
  if (STATIC && story.path) return story.path;
  return `#/story/${story.id}`;
}

function storyCard(story) {
  const card = el("article", "story-card");
  card.dataset.id = String(story.id);
  if (storyIsNew(story)) card.classList.add("is-new");
  const link = el("a", "story-link");
  link.href = storyHref(story);
  const when = formatWhen(story.published_at);
  if (when || storyIsNew(story)) {
    const kicker = el("p", "kicker");
    if (storyIsNew(story)) kicker.append(el("span", "new-mark", "New"));
    if (when) kicker.append(document.createTextNode(storyIsNew(story) ? ` · ${when}` : when));
    link.append(kicker);
  }
  link.append(headline(story));
  link.append(el("p", "summary", story.summary));
  link.append(cardMeta(story));
  const share = el("button", "card-share");
  share.type = "button";
  share.setAttribute("aria-label", "Share story");
  share.append(shareIcon());
  share.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    const result = await shareStory(story);
    if (result === "copied") flashShareFeedback(card, "Link copied");
    else if (result === "failed") flashShareFeedback(card, "Sharing unavailable");
  });
  const save = el("button", "card-save");
  save.type = "button";
  save.append(bookmarkIcon());
  paintSave(save, isSaved(story.id));
  save.addEventListener("click", () => {
    const removing = isSaved(story.id);
    const apply = (item) => {
      toggleSaved(item);
      if (route().name === "saved") {
        showSaved();
        return;
      }
      paintSave(save, isSaved(item.id));
    };
    if (!removing && !itemHasArticles(story) && !STATIC) {
      fetchJson(`/feed/${story.id}`).then(apply).catch(() => apply(story));
      return;
    }
    apply(story);
  });
  card.append(link, share, save);
  return card;
}

function itemHasArticles(story) {
  return Array.isArray(story.articles) && story.articles.length > 0;
}

function renderList(stories, { heading, note, more } = {}) {
  clear(main);
  if (heading) main.append(el("p", "meta feed-status", heading));
  if (note) main.append(el("p", "notice freshness", note));
  if (!stories.length) {
    const empty = heading && heading.startsWith("Results") ? "No stories match that search." : "No stories in this list.";
    main.append(el("p", "notice", empty));
    return;
  }
  for (const story of stories) main.append(storyCard(story));
  if (more) {
    const button = el("button", "secondary more", "Load more");
    button.type = "button";
    button.addEventListener("click", more);
    main.append(button);
  }
}

function renderStory(story, { offline = false } = {}) {
  clear(main);
  renderCategories(story.category || "");
  const article = el("article", "story");
  const back = el("a", "back", "Back");
  back.href = "#/";
  back.setAttribute("aria-label", "Back to latest");
  article.append(back);
  document.title = story.title ? `${story.title} · Edulens360` : "Edulens360";
  const originLabel = isOriginalTip(story) ? "Edulens360 tip" : sourceLabel(story.source_count);
  article.append(
    el(
      "p",
      "kicker",
      `${label(story.category)} · ${formatWhen(story.published_at)} · ${originLabel}`,
    ),
  );
  article.append(headline(story));
  article.append(el("p", "summary", story.summary));
  if (offline) article.append(el("p", "meta", "Saved on this device."));
  const actions = el("div", "actions");
  const share = el("button", "secondary", "Share");
  share.type = "button";
  share.addEventListener("click", async () => {
    const result = await shareStory(story);
    if (result === "copied") {
      share.textContent = "Link copied";
      flashShareFeedback(article, "Link copied");
    } else if (result === "failed") {
      flashShareFeedback(article, "Sharing unavailable");
    }
  });
  const save = el("button", isSaved(story.id) ? "secondary" : "", isSaved(story.id) ? "Remove save" : "Save");
  save.type = "button";
  save.addEventListener("click", () => {
    toggleSaved(story);
    renderStory(story, { offline });
  });
  actions.append(share, save);
  article.append(actions);
  for (const item of story.articles || []) {
    const block = el("section", "source");
    block.append(el("h3", "", item.source_name));
    const excerpt =
      item.source_name === "Edulens360" ? tipLead(item.excerpt) : item.excerpt;
    if (excerpt) block.append(el("p", "summary", excerpt));
    const link = el("a", "link-button secondary", `Read at ${item.source_name}`);
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    block.append(link);
    article.append(block);
  }
  main.append(article);
}

function renderMessage(text) {
  clear(main);
  main.append(el("p", "notice", text));
}

async function showLatest(current, offset = 0) {
  renderCategories(current.category || "");
  let stories;
  if (STATIC) {
    stories = staticStories(current, offset);
  } else {
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
    let url = "/feed";
    if (current.q) {
      params.delete("offset");
      params.set("q", current.q);
      url = `/feed/search?${params}`;
    } else {
      if (current.category) params.set("category", current.category);
      url = `/feed?${params}`;
    }
    stories = await fetchJson(url);
  }
  const heading = current.q ? `Results for “${current.q}”` : updatedHeading(current, stories);
  const existing = offset === 0 ? [] : [...main.querySelectorAll(".story-card")].map((card) => card.dataset.id);
  if (offset === 0) {
    renderList(stories, {
      heading,
      more: stories.length === PAGE_SIZE ? () => showLatest(current, offset + PAGE_SIZE).catch(showFailure) : null,
    });
    return;
  }
  const button = main.querySelector(".more");
  if (button) button.remove();
  for (const story of stories) {
    if (existing.includes(String(story.id))) continue;
    main.append(storyCard(story));
  }
  if (stories.length === PAGE_SIZE) {
    const more = el("button", "secondary more", "Load more");
    more.type = "button";
    more.addEventListener("click", () => showLatest(current, offset + PAGE_SIZE).catch(showFailure));
    main.append(more);
  }
}

function showSaved() {
  renderCategories("");
  const stories = savedStories();
  if (!stories.length) {
    clear(main);
    main.append(el("p", "notice", "Stories you save stay on this device."));
    const latest = el("a", "link-button", "Browse latest");
    latest.href = "#/";
    main.append(latest);
    return;
  }
  renderList(stories, { heading: "Saved on this device" });
}

async function showStory(id) {
  try {
    let story;
    if (STATIC) {
      if (!catalog) throw new Error("The feed could not be loaded.");
      story = (catalog.stories || []).find((item) => item.id === id);
      if (!story) {
        const missing = new Error("That story is not on the feed.");
        missing.status = 404;
        throw missing;
      }
    } else {
      story = await fetchJson(`/feed/${id}`);
    }
    renderStory(story);
  } catch (error) {
    const saved = savedStories().find((story) => story.id === id);
    if (!saved) throw error;
    renderStory(saved, { offline: true });
  }
  window.scrollTo(0, 0);
  requestAnimationFrame(() => window.scrollTo(0, 0));
}

function showFailure(error) {
  if (error && error.status === 404) {
    renderMessage("That story is not on the feed.");
    return;
  }
  renderMessage("The feed is not reachable. Saved stories are still on this device.");
}

async function draw() {
  const current = route();
  document.title = "Edulens360 — Ghana education news";
  searchInput.value = current.q || "";
  try {
    if (current.name === "saved") showSaved();
    else if (current.name === "story") await showStory(current.id);
    else await showLatest(current);
  } catch (error) {
    showFailure(error);
    if (current.name === "story") window.scrollTo(0, 0);
  }
}

const FEED_CACHE_KEY = "ghanaed.feed.cache.v1";

function catalogStamp(value) {
  const raw = value && value.generated_at;
  const when = Date.parse(raw || "");
  return Number.isNaN(when) ? 0 : when;
}

function applyCatalog(next, { redraw = false } = {}) {
  if (!next || !Array.isArray(next.stories)) return false;
  if (catalog && catalogStamp(next) < catalogStamp(catalog)) return false;
  catalog = next;
  categoryNames = (next.categories || []).map((item) => item.name);
  if (redraw) draw().catch(showFailure);
  return true;
}

function rememberCatalog(next) {
  try {
    sessionStorage.setItem(FEED_CACHE_KEY, JSON.stringify(next));
  } catch {
    // Session storage can be full on some phones; the live fetch still works.
  }
}

function feedDataUrl() {
  return `data/feed.json?v=${encodeURIComponent((catalog && catalog.generated_at) || "14")}`;
}

function refreshStaticCatalog() {
  return fetchJson(feedDataUrl())
    .then((fresh) => {
      if (applyCatalog(fresh, { redraw: true })) rememberCatalog(fresh);
    })
    .catch(() => {});
}

async function loadCategories() {
  try {
    if (STATIC) {
      if (catalog) {
        refreshStaticCatalog();
        return;
      }
      try {
        const cached = sessionStorage.getItem(FEED_CACHE_KEY);
        if (cached) {
          applyCatalog(JSON.parse(cached));
          refreshStaticCatalog();
          return;
        }
      } catch {
        // Ignore bad cached JSON and load from the network.
      }
      applyCatalog(await fetchJson(feedDataUrl()));
      rememberCatalog(catalog);
      return;
    }
    const categories = await fetchJson("/feed/categories");
    categoryNames = categories.map((item) => item.name);
  } catch {
    categoryNames = [];
  }
}

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = searchInput.value.trim();
  location.hash = query ? `#/search/${encodeURIComponent(query)}` : "#/";
});

function startVisit() {
  seenCutoff = readSeenAt();
  const returning = !sessionStorage.getItem(VISIT_KEY);
  sessionStorage.setItem(VISIT_KEY, "1");
  const current = route();
  if (returning && current.category) {
    pinCategory(current.category);
    history.replaceState(null, "", `${location.pathname}${location.search}#/`);
  }
}

window.addEventListener("pagehide", rememberVisit);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") rememberVisit();
});

window.addEventListener("hashchange", () => {
  const current = route();
  if (current.category) pinCategory(current.category);
  draw();
});

window.addEventListener("pageshow", () => {
  if (STATIC) refreshStaticCatalog();
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register(STATIC ? "sw.js" : "/app/sw.js").catch(() => {});
}

function adoptSearchQuery() {
  const text = (new URLSearchParams(location.search).get("q") || "").trim();
  if (!text || (location.hash && location.hash !== "#" && location.hash !== "#/")) return;
  history.replaceState(null, "", `${location.pathname}#/search/${encodeURIComponent(text)}`);
}

adoptSearchQuery();
startVisit();
loadCategories().then(draw);
