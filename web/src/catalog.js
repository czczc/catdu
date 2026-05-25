import { reactive, computed } from "vue";
import covers from "./covers.json";

const base = import.meta.env.BASE_URL;

export const imageUrl = (path) => `${base}${path}`;

export const store = reactive({
  ready: false,
  error: null,
  index: null,       // catalog.json
  shards: {},        // "<top>/<sub>": shard JSON
  catsByTop: {},     // "<top>": flat array of cats across subs
  allCats: [],       // every cat, every category
});

async function fetchJson(path) {
  const r = await fetch(`${base}${path}`);
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
  return r.json();
}

export async function loadAll() {
  if (store.ready) return;
  try {
    const index = await fetchJson("catalog.json");
    const pairs = [];
    for (const top of index.categories) {
      for (const sub of top.sub_categories) {
        pairs.push([top.slug, sub.slug]);
      }
    }
    const shardArr = await Promise.all(
      pairs.map(([top, sub]) =>
        fetchJson(`catalog/${top}/${sub}.json`).then((shard) => ({
          key: `${top}/${sub}`,
          top,
          sub,
          shard,
        })),
      ),
    );
    const shards = {};
    const catsByTop = {};
    const allCats = [];
    for (const { key, top, sub, shard } of shardArr) {
      shards[key] = shard;
      catsByTop[top] ??= [];
      for (const set of shard.sets) {
        for (const logo of set.logos) {
          const cat = {
            ...logo,
            top,
            sub,
            set_number: set.set_number,
            top_display: shard.top.display,
            sub_display: shard.sub.display,
          };
          catsByTop[top].push(cat);
          allCats.push(cat);
        }
      }
    }
    store.index = index;
    store.shards = shards;
    store.catsByTop = catsByTop;
    store.allCats = allCats;
    store.ready = true;
  } catch (e) {
    store.error = e.message || String(e);
  }
}

export function findCat(top, sub, set, slug) {
  const list = store.catsByTop[top];
  if (!list) return null;
  return list.find(
    (c) =>
      c.sub === sub &&
      c.set_number === Number(set) &&
      c.english_slug === slug,
  ) ?? null;
}

function catFromPath(path) {
  const parts = String(path).split("/");
  if (parts.length !== 4) return null;
  const [top, sub, set, slug] = parts;
  return findCat(top, sub, set, slug);
}

/** Return up to 4 cover cats for a top category.
 * Prefer hand-picked entries in covers.json. Fall back algorithmically:
 * one cat per sub (lowest source_cell), filling to 4 with extra cats from
 * the largest sub. */
export function coversFor(topSlug) {
  const list = store.catsByTop[topSlug] || [];
  if (list.length === 0) return [];
  const picks = [];
  for (const path of covers[topSlug] || []) {
    const cat = catFromPath(path);
    if (cat) picks.push(cat);
    if (picks.length === 4) return picks;
  }
  const seen = new Set(picks.map((c) => `${c.sub}/${c.english_slug}`));
  const bySub = new Map();
  for (const cat of list) {
    if (!bySub.has(cat.sub)) bySub.set(cat.sub, []);
    bySub.get(cat.sub).push(cat);
  }
  for (const arr of bySub.values()) {
    arr.sort((a, b) => (a.source_cell ?? 0) - (b.source_cell ?? 0));
  }
  for (const arr of bySub.values()) {
    const first = arr[0];
    if (first && !seen.has(`${first.sub}/${first.english_slug}`)) {
      picks.push(first);
      seen.add(`${first.sub}/${first.english_slug}`);
      if (picks.length === 4) return picks;
    }
  }
  // Still short? Fill from the biggest sub by remaining cats.
  const sortedSubs = [...bySub.values()].sort((a, b) => b.length - a.length);
  for (const arr of sortedSubs) {
    for (const cat of arr) {
      const key = `${cat.sub}/${cat.english_slug}`;
      if (!seen.has(key)) {
        picks.push(cat);
        seen.add(key);
        if (picks.length === 4) return picks;
      }
    }
  }
  return picks;
}

export const totalCats = computed(() => store.allCats.length);
export const totalCategories = computed(
  () => (store.index?.categories || []).length,
);
