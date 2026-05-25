<script setup>
import { computed } from "vue";
import { store, totalCats, totalCategories, coversFor } from "../catalog.js";
import Polaroid from "../components/Polaroid.vue";

const CATEGORY_DESCRIPTIONS = {
  mythology:
    "Gods and heroes from Olympus, Asgard, and Takamagahara — each cat dressed in their iconography.",
  geography:
    "States, provinces, and cities as cats — local food, monuments, and landscapes condensed into 200×200 pixels.",
  game:
    "Champions and characters from video games. Pulled straight from the lore.",
  institution:
    "Universities, national labs, federal agencies, and professional societies — the cats of academia.",
  science:
    "Particle physics: the Standard Model's fundamental particles and their antimatter twins, posed as cats.",
};

const cards = computed(() =>
  (store.index?.categories || []).map((top) => {
    const count = (store.catsByTop[top.slug] || []).length;
    const subs = top.sub_categories.map((s) => s.display).join(", ");
    return {
      slug: top.slug,
      display: top.display,
      count,
      subs,
      covers: coversFor(top.slug),
      description: CATEGORY_DESCRIPTIONS[top.slug] || "",
    };
  }),
);
</script>

<template>
  <main class="shell">
    <section class="masthead">
      <div class="masthead-row">
        <h1 class="headline headline-home">The cat catalog</h1>
        <span class="meta-caps">HOME / INDEX</span>
      </div>
      <p class="lede">
        AI-generated cats, organized by mythology, geography, and the rest.
        Pick a theme, or rifle through the whole index.
      </p>
      <div class="masthead-meta meta-caps">
        <span>{{ totalCats }} cats</span>
        <span class="meta-dot">·</span>
        <span>{{ totalCategories }} categories</span>
      </div>
    </section>

    <div class="rule" />

    <div class="home-grid">
      <router-link
        v-for="(card, i) in cards"
        :key="card.slug"
        :to="`/${card.slug}`"
        class="home-card"
      >
        <span class="home-card-idx">{{ String(i + 1).padStart(2, "0") }}</span>

        <div class="home-fan-wrap">
          <div class="home-fan">
            <div
              v-for="(cat, j) in card.covers"
              :key="cat.english_slug + j"
              class="home-fan-slot"
              :data-pos="j"
            >
              <Polaroid :cat="cat" :size="76" />
            </div>
          </div>
        </div>

        <div class="home-card-meta">
          <h2 class="home-card-name">{{ card.display }}</h2>
          <div class="home-card-line">
            <span class="count-accent">{{ card.count }} cats</span>
            <span class="home-card-sub">· {{ card.subs }}</span>
          </div>
          <p class="home-card-desc" v-if="card.description">
            {{ card.description }}
          </p>
          <div class="home-card-cta meta-caps">
            <span>Browse</span>
            <span class="arrow">→</span>
          </div>
        </div>
      </router-link>
    </div>
  </main>
</template>
