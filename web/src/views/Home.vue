<script setup>
import { ref, onMounted } from "vue";
import { loadCatalog, loadShard, imageUrl } from "../catalog.js";
import { href } from "../router.js";

const cards = ref(null);

onMounted(async () => {
  const catalog = await loadCatalog();
  const out = [];
  for (const top of catalog.categories) {
    const covers = [];
    let total = 0;
    for (const sub of top.sub_categories) {
      total += sub.logo_count;
      if (covers.length < 4) {
        const shard = await loadShard(top.slug, sub.slug);
        for (const set of shard.sets) {
          for (const logo of set.logos) {
            if (covers.length < 4) covers.push(logo);
          }
        }
      }
    }
    out.push({
      slug: top.slug,
      display: top.display,
      sub_categories: top.sub_categories,
      total,
      covers,
    });
  }
  cards.value = out;
});

const rotations = ["-6deg", "3deg", "-2deg", "5deg"];
</script>

<template>
  <div>
    <div class="section-head">
      <h2>The cat catalog</h2>
      <span class="crumb">Home</span>
    </div>
    <p class="section-sub">
      AI-generated cats, organized by mythology, zodiac, and the rest. Pick a
      theme.
    </p>
    <hr class="double-rule" />

    <p v-if="!cards" class="loading">Loading…</p>
    <ul v-else class="top-list">
      <li v-for="top in cards" :key="top.slug">
        <a class="top-card" :href="href({ name: 'sub', top: top.slug, sub: top.sub_categories[0].slug })">
          <div class="top-card-covers">
            <img
              v-for="(c, i) in top.covers"
              :key="c.id"
              :src="imageUrl(c.image_path)"
              :alt="c.english_name"
              :style="{ '--r': rotations[i] || '0deg' }"
            />
          </div>
          <h3>{{ top.display }}</h3>
          <div class="sub-list">
            <span class="count">{{ top.total }} cats</span>
            <span> · {{ top.sub_categories.map((s) => s.display).join(", ") }}</span>
          </div>
        </a>
      </li>
    </ul>
  </div>
</template>
