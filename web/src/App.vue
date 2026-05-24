<script setup>
import { ref, onMounted } from "vue";

const base = import.meta.env.BASE_URL;
const shard = ref(null);
const error = ref(null);

onMounted(async () => {
  try {
    const catalog = await fetch(`${base}catalog.json`).then((r) => r.json());
    // Tracer: load the first sub-category's shard. Slice #5 adds routing/browse.
    const top = catalog.categories[0];
    const sub = top.sub_categories[0];
    shard.value = await fetch(
      `${base}catalog/${top.slug}/${sub.slug}.json`,
    ).then((r) => r.json());
  } catch (e) {
    error.value = e.message;
  }
});
</script>

<template>
  <main>
    <template v-if="shard">
      <h1>{{ shard.sub.display }} {{ shard.top.display }}</h1>
      <p class="subtitle">
        {{ shard.sets.reduce((n, s) => n + s.logos.length, 0) }} logos across
        {{ shard.sets.length }} set{{ shard.sets.length === 1 ? "" : "s" }}.
      </p>
      <section v-for="set in shard.sets" :key="set.set_number">
        <h2>Set {{ set.set_number }}: {{ set.display }}</h2>
        <p class="style-desc">{{ set.style_description }}</p>
        <div class="logos">
          <figure v-for="logo in set.logos" :key="logo.id">
            <img
              :src="`${base}${logo.image_path}`"
              :alt="logo.english_name"
              width="200"
              height="200"
            />
            <figcaption>
              <div>
                <span class="name">{{ logo.english_name }}</span>
                <span v-if="logo.chinese_name" class="chinese"
                  >{{ logo.chinese_name }}</span
                >
              </div>
              <a
                v-if="logo.wiki_url"
                class="wiki"
                :href="logo.wiki_url"
                target="_blank"
                rel="noopener"
                >wiki ↗</a
              >
              <div class="iconography">
                <span
                  v-for="icon in logo.iconography"
                  :key="icon"
                  class="chip"
                  >{{ icon }}</span
                >
              </div>
            </figcaption>
          </figure>
        </div>
      </section>
    </template>
    <p v-else-if="error" class="loading">Failed to load catalog: {{ error }}</p>
    <p v-else class="loading">Loading…</p>
  </main>
</template>
