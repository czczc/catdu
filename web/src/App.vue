<script setup>
import { onMounted } from "vue";
import { store, loadAll } from "./catalog.js";
import AppHeader from "./components/AppHeader.vue";

onMounted(() => {
  loadAll();
});
</script>

<template>
  <div v-if="!store.ready && !store.error" class="skeleton" aria-busy="true">
    <div class="skeleton-title" />
    <div class="skeleton-lede" />
    <div class="skeleton-grid">
      <div class="skeleton-card" />
      <div class="skeleton-card" />
      <div class="skeleton-card" />
      <div class="skeleton-card" />
    </div>
  </div>
  <div v-else-if="store.error" class="notfound">
    <h1>Failed to load.</h1>
    <p>{{ store.error }}</p>
  </div>
  <template v-else>
    <AppHeader />
    <router-view />
  </template>
</template>
