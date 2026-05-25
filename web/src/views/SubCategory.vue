<script setup>
import { ref, computed, watch } from "vue";
import { loadCatalog, loadShard, imageUrl } from "../catalog.js";
import { route, href } from "../router.js";

const shard = ref(null);
const catalog = ref(null);
const activeSetIdx = ref(0);

async function load() {
  shard.value = null;
  activeSetIdx.value = 0;
  const [c, s] = await Promise.all([
    loadCatalog(),
    loadShard(route.value.top, route.value.sub),
  ]);
  catalog.value = c;
  shard.value = s;
}

watch(
  () => `${route.value.top}/${route.value.sub}`,
  () => load(),
  { immediate: true },
);

const siblingSubs = computed(() => {
  if (!catalog.value || !shard.value) return [];
  const top = catalog.value.categories.find((t) => t.slug === shard.value.top.slug);
  return top?.sub_categories || [];
});

const activeSet = computed(() => shard.value?.sets[activeSetIdx.value]);
const sortedLogos = computed(() =>
  activeSet.value
    ? [...activeSet.value.logos].sort((a, b) =>
        a.english_name.localeCompare(b.english_name),
      )
    : [],
);
</script>

<template>
  <div v-if="!shard" class="loading">Loading…</div>
  <div v-else>
    <div class="crumb-nav">
      <a :href="href({ name: 'home' })">Home</a>
      <span> / {{ shard.top.display }}</span>
    </div>
    <div class="section-head">
      <h2>{{ shard.sub.display }} {{ shard.top.display }}</h2>
      <span class="crumb"
        >{{ shard.sets.reduce((n, s) => n + s.logos.length, 0) }} cats ·
        {{ shard.sets.length }} set{{ shard.sets.length === 1 ? "" : "s" }}</span
      >
    </div>
    <p class="section-sub" v-if="activeSet">
      {{ activeSet.style_description }}
    </p>
    <hr class="double-rule" />

    <div class="set-tabs" v-if="siblingSubs.length > 1">
      <a
        v-for="sub in siblingSubs"
        :key="sub.slug"
        class="set-tab"
        :class="{ active: sub.slug === shard.sub.slug }"
        :href="href({ name: 'sub', top: shard.top.slug, sub: sub.slug })"
      >
        {{ sub.display }}
        <span class="set-tab-count">{{ sub.logo_count }}</span>
      </a>
    </div>

    <div class="set-tabs" v-if="shard.sets.length > 1">
      <button
        v-for="(set, idx) in shard.sets"
        :key="set.set_number"
        class="set-tab"
        :class="{ active: idx === activeSetIdx }"
        @click="activeSetIdx = idx"
      >
        Set {{ set.set_number }} · {{ set.display }}
      </button>
    </div>

    <ul class="logo-grid" v-if="activeSet">
      <li v-for="logo in sortedLogos" :key="logo.id">
        <a
          class="logo-card"
          :href="href({
            name: 'logo',
            top: shard.top.slug,
            sub: shard.sub.slug,
            set: activeSet.set_number,
            slug: logo.english_slug,
          })"
        >
          <img
            :src="imageUrl(logo.image_path)"
            :alt="logo.english_name"
            loading="lazy"
          />
          <span class="name">{{ logo.english_name }}</span>
          <span v-if="logo.chinese_name" class="chinese">{{
            logo.chinese_name
          }}</span>
        </a>
      </li>
    </ul>
  </div>
</template>
