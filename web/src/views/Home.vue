<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import { store, totalCats, totalCategories, coversFor, searchCats, imageUrl } from "../catalog.js";
import Polaroid from "../components/Polaroid.vue";

const COVER_TILTS = ["-6deg", "3deg", "-2deg", "5deg"];

const route = useRoute();
const query = computed(() => String(route.query.q || "").trim());
const searchResults = computed(() => {
  if (!query.value) return null;
  return searchCats(query.value, store.allCats);
});

const CATEGORY_DESCRIPTIONS = {
  mythology: "Gods, heroes, and monsters from the world's mythologies.",
  geography: "Countries, regions, and landmarks from around the globe.",
  game: "Characters from the worlds of video games.",
  academia: "Universities, research labs, and institutions.",
  science: "The building blocks of the universe.",
  food: "Iconic dishes from the world's kitchens.",
  art: "Masterpieces from the history of art.",
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
        <h1 class="headline headline-home">Welcome to the Cat Dimension</h1>
      </div>
      <div class="masthead-lede-row">
        <p class="lede">
          A growing gallery of cute cat avatars reimagined as anything with a
          story worth telling. Browse by department.
        </p>
        <div class="masthead-meta meta-caps">
          <span class="count-accent">{{ totalCats }} cats</span>
          <span class="meta-dot">·</span>
          <span>{{ totalCategories }} categories</span>
        </div>
      </div>
    </section>

    <div class="rule" />

    <template v-if="searchResults">
      <p class="search-results-meta">
        {{ searchResults.length }} match{{ searchResults.length === 1 ? "" : "es" }}
        for "{{ query }}"
      </p>
      <div v-if="searchResults.length === 0" class="empty">
        <h2 class="empty-title">No matches.</h2>
        <p class="lede">Try a different word, or clear the search.</p>
      </div>
      <div v-else class="thumb-grid">
        <router-link
          v-for="cat in searchResults"
          :key="`${cat.top}/${cat.sub}/${cat.set_number}/${cat.english_slug}`"
          :to="`/${cat.top}/${cat.sub}/${cat.set_number}/${cat.english_slug}`"
          class="thumb"
        >
          <Polaroid :cat="cat" :size="150" />
          <div class="thumb-meta">
            <h3 class="thumb-name">{{ cat.english_name }}</h3>
            <div class="thumb-line">
              <span class="thumb-chinese">
                {{ cat.chinese_name || `${cat.top_display} · ${cat.sub_display}` }}
              </span>
            </div>
          </div>
        </router-link>
      </div>
    </template>

    <div v-else class="home-grid">
      <router-link
        v-for="card in cards"
        :key="card.slug"
        :to="`/${card.slug}`"
        class="home-card"
      >
        <div class="home-stack">
          <img
            v-for="(cat, j) in card.covers"
            :key="cat.english_slug + j"
            :src="imageUrl(cat.image_path)"
            :alt="cat.english_name"
            class="home-stack-cover"
            :style="{ '--tilt': COVER_TILTS[j] || '0deg' }"
            width="88"
            height="88"
          />
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
        </div>
      </router-link>
    </div>

  </main>
</template>
