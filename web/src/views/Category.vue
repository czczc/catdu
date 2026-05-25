<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { store, findCat } from "../catalog.js";
import Polaroid from "../components/Polaroid.vue";

const route = useRoute();
const router = useRouter();

const top = computed(() => route.params.top);
const sub = computed(() => route.params.sub || null);

const topMeta = computed(() =>
  (store.index?.categories || []).find((c) => c.slug === top.value),
);

const subEntries = computed(() => {
  // List of {slug, display, count} for the chip rail.
  const cats = store.catsByTop[top.value] || [];
  const counts = new Map();
  for (const c of cats) {
    counts.set(c.sub, (counts.get(c.sub) || 0) + 1);
  }
  return (topMeta.value?.sub_categories || []).map((s) => ({
    slug: s.slug,
    display: s.display,
    count: counts.get(s.slug) || 0,
  }));
});

const sortMode = computed(() => {
  const q = String(route.query.sort || "curated").toLowerCase();
  return ["curated", "az", "za"].includes(q) ? q : "curated";
});

const cats = computed(() => {
  const all = (store.catsByTop[top.value] || []).filter(
    (c) => !sub.value || c.sub === sub.value,
  );
  const arr = [...all];
  if (sortMode.value === "az") {
    arr.sort((a, b) => a.english_name.localeCompare(b.english_name));
  } else if (sortMode.value === "za") {
    arr.sort((a, b) => b.english_name.localeCompare(a.english_name));
  } else {
    // Curated = sheet order. Within mixed subs, also key on sub to keep
    // related cats together.
    arr.sort(
      (a, b) =>
        a.sub.localeCompare(b.sub) ||
        (a.source_cell ?? 0) - (b.source_cell ?? 0),
    );
  }
  return arr;
});

const subDisplayList = computed(() =>
  (topMeta.value?.sub_categories || []).map((s) => s.display).join(", "),
);

function setSub(nextSlug) {
  // null/"all" = clear the sub filter.
  const params = nextSlug
    ? { top: top.value, sub: nextSlug }
    : { top: top.value };
  router.replace({ name: nextSlug ? "sub" : "top", params, query: route.query });
}

function setSort(e) {
  const next = e.target.value;
  const query = { ...route.query };
  if (next === "curated") delete query.sort;
  else query.sort = next;
  router.replace({ ...route, query });
}

// Detail-route co-mount (still stubbed until #12)
const detailCat = computed(() => {
  if (route.name !== "detail") return null;
  return findCat(
    route.params.top,
    route.params.sub,
    route.params.set,
    route.params.slug,
  );
});
</script>

<template>
  <main class="shell" v-if="topMeta">
    <section class="masthead">
      <div class="cat-masthead-row">
        <h1 class="headline headline-cat">{{ topMeta.display }}</h1>
        <div class="cat-masthead-meta meta-caps">
          <span class="count-accent">{{ (store.catsByTop[top] || []).length }} cats</span>
          <span class="meta-dot">·</span>
          <span>{{ subDisplayList }}</span>
        </div>
      </div>
    </section>

    <div class="rule" />

    <div class="filter-bar">
      <div class="chip-row">
        <button
          type="button"
          class="chip"
          :class="{ 'chip-on': !sub }"
          @click="setSub(null)"
        >
          All
          <span class="chip-count">{{ (store.catsByTop[top] || []).length }}</span>
        </button>
        <button
          v-for="entry in subEntries"
          :key="entry.slug"
          type="button"
          class="chip"
          :class="{ 'chip-on': sub === entry.slug }"
          @click="setSub(entry.slug)"
        >
          {{ entry.display }}
          <span class="chip-count">{{ entry.count }}</span>
        </button>
      </div>
      <label class="sort">
        <span class="sort-label">Sort</span>
        <select :value="sortMode" @change="setSort">
          <option value="curated">Curated</option>
          <option value="az">A–Z</option>
          <option value="za">Z–A</option>
        </select>
      </label>
    </div>

    <div v-if="cats.length === 0" class="empty">
      <h2 class="empty-title">No cats in this row.</h2>
      <p class="lede">Pick a different filter, or browse the whole catalog.</p>
    </div>
    <div v-else class="thumb-grid">
      <router-link
        v-for="cat in cats"
        :key="`${cat.sub}/${cat.set_number}/${cat.english_slug}`"
        :to="`/${cat.top}/${cat.sub}/${cat.set_number}/${cat.english_slug}`"
        class="thumb"
      >
        <Polaroid :cat="cat" :size="170" />
        <div class="thumb-meta">
          <h3 class="thumb-name">{{ cat.english_name }}</h3>
          <div class="thumb-line">
            <span>{{ cat.sub_display }}</span>
            <span class="thumb-id">
              #{{ String(cat.source_cell ?? 0).padStart(3, "0") }}
            </span>
          </div>
        </div>
      </router-link>
    </div>

    <div
      v-if="detailCat"
      class="meta-caps"
      style="margin-top: 32px; text-align: center"
    >
      detail stub for "{{ detailCat.english_name }}" — pane lands in #12 ·
      <router-link :to="`/${top}/${detailCat.sub}`">close</router-link>
    </div>
  </main>
  <main class="notfound" v-else>
    <h1>Not found.</h1>
    <p>no category named "{{ top }}"</p>
    <router-link to="/">← Back to home</router-link>
  </main>
</template>
