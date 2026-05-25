import { reactive, computed } from "vue";

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

export const totalCats = computed(() => store.allCats.length);
export const totalCategories = computed(
  () => (store.index?.categories || []).length,
);
