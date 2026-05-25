<script setup>
import { ref, computed, watch } from "vue";
import { loadShard, imageUrl } from "../catalog.js";
import { route, href } from "../router.js";

const shard = ref(null);

async function load() {
  shard.value = null;
  shard.value = await loadShard(route.value.top, route.value.sub);
}

watch(
  () => `${route.value.top}/${route.value.sub}`,
  () => load(),
  { immediate: true },
);

const activeSet = computed(
  () => shard.value?.sets.find((s) => s.set_number === route.value.set) || null,
);

const logo = computed(
  () =>
    activeSet.value?.logos.find((l) => l.english_slug === route.value.slug) ||
    null,
);

const acrossSets = computed(() => {
  if (!shard.value || !logo.value) return [];
  return shard.value.sets
    .filter((s) => s.set_number !== route.value.set)
    .map((s) => ({
      set: s,
      match: s.logos.find((l) => l.english_slug === logo.value.english_slug),
    }))
    .filter((x) => x.match);
});
</script>

<template>
  <div v-if="!shard" class="loading">Loading…</div>
  <div v-else-if="!logo" class="loading">
    Not found.
    <a :href="href({ name: 'sub', top: route.top, sub: route.sub })"
      >Back to {{ shard.sub.display }} {{ shard.top.display }}</a
    >
  </div>
  <div v-else>
    <div class="crumb-nav">
      <a :href="href({ name: 'home' })">Home</a>
      <span> / </span>
      <a :href="href({ name: 'sub', top: shard.top.slug, sub: shard.sub.slug })"
        >{{ shard.sub.display }} {{ shard.top.display }}</a
      >
      <span> / Set {{ activeSet.set_number }}</span>
    </div>

    <div class="logo-detail">
      <div class="logo-detail-hero">
        <img :src="imageUrl(logo.image_path)" :alt="logo.english_name" />
      </div>
      <div class="logo-detail-meta">
        <h1>{{ logo.english_name }}</h1>
        <p v-if="logo.chinese_name" class="chinese">{{ logo.chinese_name }}</p>
        <p class="set-ctx">
          {{ shard.top.display }} · {{ shard.sub.display }} · Set
          {{ activeSet.set_number }} · {{ activeSet.display }}
        </p>
        <p v-if="logo.summary" class="summary">{{ logo.summary }}</p>
        <a
          v-if="logo.wiki_url"
          class="wiki"
          :href="logo.wiki_url"
          target="_blank"
          rel="noopener"
          >Wikipedia ↗</a
        >
        <div v-if="logo.iconography?.length">
          <div class="icon-label">Iconography</div>
          <div class="chips">
            <span v-for="ic in logo.iconography" :key="ic" class="chip">{{
              ic
            }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="across" v-if="acrossSets.length">
      <h3>Across sets</h3>
      <div class="across-grid">
        <a
          v-for="entry in acrossSets"
          :key="entry.set.set_number"
          class="logo-card"
          :href="href({
            name: 'logo',
            top: shard.top.slug,
            sub: shard.sub.slug,
            set: entry.set.set_number,
            slug: entry.match.english_slug,
          })"
        >
          <img
            :src="imageUrl(entry.match.image_path)"
            :alt="entry.match.english_name"
          />
          <span class="num">Set {{ entry.set.set_number }}</span>
          <span class="name">{{ entry.match.english_name }}</span>
        </a>
      </div>
    </div>
  </div>
</template>
