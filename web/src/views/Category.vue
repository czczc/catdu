<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import { store, findCat } from "../catalog.js";

const route = useRoute();

const top = computed(() => route.params.top);
const sub = computed(() => route.params.sub);

const topMeta = computed(() =>
  (store.index?.categories || []).find((c) => c.slug === top.value),
);

const cats = computed(() => {
  const all = store.catsByTop[top.value] || [];
  if (!sub.value) return all;
  return all.filter((c) => c.sub === sub.value);
});

const detailCat = computed(() => {
  if (route.name !== "detail") return null;
  return findCat(top.value, sub.value, route.params.set, route.params.slug);
});
</script>

<template>
  <main class="shell placeholder-page" v-if="topMeta">
    <p class="placeholder-meta">
      <router-link to="/">HOME</router-link> /
      {{ topMeta.display.toUpperCase() }}
      <template v-if="sub"> / {{ sub.toUpperCase() }}</template>
      <template v-if="detailCat"> / {{ detailCat.english_name.toUpperCase() }}</template>
    </p>
    <h1 class="placeholder-title">{{ topMeta.display }}</h1>
    <p class="placeholder-meta">
      {{ cats.length }} cats · tracer build
    </p>
    <ul class="placeholder-list">
      <li v-for="cat in cats" :key="`${cat.sub}/${cat.set_number}/${cat.english_slug}`">
        <router-link
          :to="`/${cat.top}/${cat.sub}/${cat.set_number}/${cat.english_slug}`"
        >
          {{ cat.english_name }}
          <span class="placeholder-count">{{ cat.sub }}</span>
        </router-link>
      </li>
    </ul>
    <div v-if="detailCat" class="placeholder-meta" style="margin-top: 32px">
      detail stub: {{ detailCat.english_name }} —
      <router-link :to="`/${top}/${sub || detailCat.sub}`">close</router-link>
    </div>
  </main>
  <main class="notfound" v-else>
    <h1>Not found.</h1>
    <p>no category named "{{ top }}"</p>
    <router-link to="/">← Back to home</router-link>
  </main>
</template>
