<script setup>
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { store } from "../catalog.js";

const route = useRoute();
const router = useRouter();

const local = ref(String(route.query.q || ""));
let debounceTimer = null;

// Sync local → URL with debounce
watch(local, (next) => {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    const trimmed = next.trim();
    const query = { ...route.query };
    if (trimmed) query.q = trimmed;
    else delete query.q;
    router.replace({ path: route.path, query });
  }, 250);
});

// Sync URL → local when changed externally (e.g. clicking brand)
watch(
  () => route.query.q,
  (next) => {
    const v = String(next || "");
    if (v !== local.value) local.value = v;
  },
);

function clearSearch() {
  local.value = "";
}

const topMeta = computed(() => {
  if (!route.params.top) return null;
  return (store.index?.categories || []).find(
    (c) => c.slug === route.params.top,
  );
});

const subMeta = computed(() => {
  if (!topMeta.value || !route.params.sub) return null;
  return topMeta.value.sub_categories.find((s) => s.slug === route.params.sub);
});

</script>

<template>
  <header class="hdr">
    <div class="hdr-inner">
      <router-link to="/" class="brand" aria-label="Home">
        <span class="brand-mark">Meowphosis</span>
      </router-link>
      <nav class="crumb" aria-label="Breadcrumb">
        <router-link v-if="route.name !== 'home'" to="/">HOME</router-link>
        <span v-else class="crumb-current">HOME</span>
        <template v-if="topMeta">
          <span class="crumb-sep">/</span>
          <router-link
            v-if="subMeta || route.name === 'detail'"
            :to="`/${topMeta.slug}`"
            >{{ topMeta.display.toUpperCase() }}</router-link
          >
          <span v-else class="crumb-current">{{
            topMeta.display.toUpperCase()
          }}</span>
        </template>
        <template v-if="subMeta">
          <span class="crumb-sep">/</span>
          <router-link
            v-if="route.name === 'detail'"
            :to="`/${topMeta.slug}/${subMeta.slug}`"
            >{{ subMeta.display.toUpperCase() }}</router-link
          >
          <span v-else class="crumb-current">{{
            subMeta.display.toUpperCase()
          }}</span>
        </template>
        <template v-if="route.name === 'detail'">
          <span class="crumb-sep">/</span>
          <span class="crumb-current">{{
            String(route.params.slug).toUpperCase()
          }}</span>
        </template>
      </nav>
      <div class="hdr-search" role="search">
        <span class="hdr-search-icon" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="7" cy="7" r="5" stroke="currentColor" stroke-width="1.4" />
            <path d="m11 11 3 3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
          </svg>
        </span>
        <input
          type="search"
          v-model="local"
          placeholder="Search name, sub, iconography…"
          aria-label="Search the catalog"
        />
        <button
          v-if="local"
          type="button"
          class="hdr-search-x"
          @click="clearSearch"
          aria-label="Clear search"
        >
          ×
        </button>
      </div>
    </div>
  </header>
</template>
