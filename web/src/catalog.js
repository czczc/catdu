const base = import.meta.env.BASE_URL;

let catalogPromise = null;
const shardCache = new Map();

export function loadCatalog() {
  if (!catalogPromise) {
    catalogPromise = fetch(`${base}catalog.json`).then((r) => r.json());
  }
  return catalogPromise;
}

export function loadShard(top, sub) {
  const key = `${top}/${sub}`;
  if (!shardCache.has(key)) {
    shardCache.set(
      key,
      fetch(`${base}catalog/${top}/${sub}.json`).then((r) => r.json()),
    );
  }
  return shardCache.get(key);
}

export async function loadAllShards() {
  const catalog = await loadCatalog();
  const shards = [];
  for (const top of catalog.categories) {
    for (const sub of top.sub_categories) {
      shards.push(await loadShard(top.slug, sub.slug));
    }
  }
  return shards;
}

export function imageUrl(path) {
  return `${base}${path}`;
}
