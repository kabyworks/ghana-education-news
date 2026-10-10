const SAVED_KEY = "ghanaed.saved.v1";
const PAGE_SIZE = 20;

const CATEGORY_LABELS = {
  teachers: "Teachers",
  higher_education: "Higher education",
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
const searchToggle = document.querySelector("#search-toggle");
let searchOpen = false;
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

function publishers(count) {
  return count === 1 ? "1 publisher" : `${count} publishers`;
}

function searchTerms(query) {
  return (query.toLowerCase().match(/[a-z0-9]+/g) || []).filter((term) => term.length >= 2);
}

function matchesStory(story, terms) {
  const haystack = [story.title, story.summary, ...(story.articles || []).map((article) => article.title)]
    .join(" ")
    .toLowerCase();
  return terms.every((term) => new RegExp(`\\b${term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`).test(haystack));
}

function staticStories(current, offset) {
  if (!catalog) throw new Error("The feed could not be loaded.");
  let stories = catalog.stories || [];
  if (current.category) stories = stories.filter((story) => story.category === current.category);
  if (current.q) {
    const terms = searchTerms(current.q);
    stories = terms.length ? stories.filter((story) => matchesStory(story, terms)) : [];
  }
  return stories.slice(offset, offset + PAGE_SIZE);
}

function updatedHeading() {
  if (!STATIC || !catalog || !catalog.generated_at) return "";
  const date = new Date(catalog.generated_at);
  if (Number.isNaN(date.getTime())) return "";
  const when = date.toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
  return `Updated ${when}`;
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

function renderCategories(active) {
  clear(categoriesEl);
  const current = route();
  categoriesEl.hidden = current.name === "story";
  if (current.name === "story") return;
  const latest = el("a", "", "Latest");
  latest.href = "#/";
  if (current.name === "latest" && !active) latest.setAttribute("aria-current", "true");
  categoriesEl.append(latest);
  const shown = categoriesExpanded ? categoryNames : categoryNames.slice(0, 2);
  if (!categoriesExpanded && active && !shown.includes(active)) shown.push(active);
  for (const name of shown) {
    const link = el("a", "", label(name));
    link.href = `#/category/${encodeURIComponent(name)}`;
    if (name === active) link.setAttribute("aria-current", "true");
    categoriesEl.append(link);
  }
  if (categoryNames.length > 2) {
    const more = el("button", "more-cats", categoriesExpanded ? "–" : "+");
    more.type = "button";
    more.setAttribute("aria-expanded", categoriesExpanded ? "true" : "false");
    more.setAttribute("aria-label", categoriesExpanded ? "Show fewer categories" : "Show more categories");
    more.addEventListener("click", () => {
      categoriesExpanded = !categoriesExpanded;
      renderCategories(active);
    });
    categoriesEl.append(more);
  }
  const saved = el("a", "", "Saved");
  saved.href = "#/saved";
  if (current.name === "saved") saved.setAttribute("aria-current", "true");
  categoriesEl.append(saved);
}

function storyCard(story) {
  const card = el("a", "story-card");
  card.href = `#/story/${story.id}`;
  card.dataset.id = String(story.id);
  card.append(el("p", "kicker", `${label(story.category)} · ${formatWhen(story.published_at)}`));
  card.append(el("h2", "", story.title));
  card.append(el("p", "summary", story.summary));
  card.append(el("p", "meta", publishers(story.source_count)));
  return card;
}

function renderList(stories, { heading, more } = {}) {
  clear(main);
  if (heading) main.append(el("p", "meta", heading));
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
  const article = el("article", "story");
  const back = el("a", "back", "Back");
  back.href = "#/";
  back.setAttribute("aria-label", "Back to latest");
  article.append(back);
  document.title = story.title ? `${story.title} · Edulens360` : "Edulens360";
  article.append(el("p", "kicker", `${label(story.category)} · ${formatWhen(story.published_at)} · ${publishers(story.source_count)}`));
  article.append(el("h2", "", story.title));
  article.append(el("p", "summary", story.summary));
  if (offline) article.append(el("p", "meta", "Saved on this device."));
  const actions = el("div", "actions");
  const save = el("button", isSaved(story.id) ? "secondary" : "", isSaved(story.id) ? "Remove save" : "Save");
  save.type = "button";
  save.addEventListener("click", () => {
    toggleSaved(story);
    renderStory(story, { offline });
  });
  actions.append(save);
  article.append(actions);
  for (const item of story.articles || []) {
    const block = el("section", "source");
    block.append(el("h3", "", item.source_name));
    if (item.excerpt) block.append(el("p", "summary", item.excerpt));
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
  const heading = current.q ? `Results for “${current.q}”` : updatedHeading();
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
    renderMessage("Stories you save stay on this device.");
    return;
  }
  renderList(stories, { heading: "Saved on this device" });
}

async function showStory(id) {
  categoriesEl.hidden = true;
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

function syncSearch(current) {
  if (current.name !== "latest") searchOpen = false;
  const open = searchOpen && current.name === "latest";
  searchForm.hidden = !open;
  searchToggle.setAttribute("aria-expanded", open ? "true" : "false");
  if (open) searchInput.focus();
}

async function draw() {
  const current = route();
  document.title = "Edulens360";
  if (current.q) searchOpen = true;
  searchInput.value = current.q || "";
  try {
    if (current.name === "saved") showSaved();
    else if (current.name === "story") await showStory(current.id);
    else await showLatest(current);
  } catch (error) {
    showFailure(error);
    if (current.name === "story") window.scrollTo(0, 0);
  }
  syncSearch(current);
}

async function loadCategories() {
  try {
    if (STATIC) {
      catalog = await fetchJson("data/feed.json");
      categoryNames = (catalog.categories || []).map((item) => item.name);
      return;
    }
    const categories = await fetchJson("/feed/categories");
    categoryNames = categories.map((item) => item.name);
  } catch {
    categoryNames = [];
  }
}

searchToggle.addEventListener("click", () => {
  const current = route();
  if (current.name !== "latest") {
    searchOpen = true;
    location.hash = "#/";
    return;
  }
  searchOpen = !searchOpen;
  syncSearch(current);
});

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = searchInput.value.trim();
  location.hash = query ? `#/search/${encodeURIComponent(query)}` : "#/";
});

window.addEventListener("hashchange", () => {
  draw();
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register(STATIC ? "sw.js" : "/app/sw.js").catch(() => {});
}

loadCategories().then(draw);
