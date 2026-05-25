<script setup>
import { store, totalCats, totalCategories } from "../catalog.js";
</script>

<template>
  <main class="shell placeholder-page">
    <p class="placeholder-meta">HOME / INDEX</p>
    <h1 class="placeholder-title">The cat catalog</h1>
    <p class="placeholder-meta">
      {{ totalCats }} cats · {{ totalCategories }} categories · tracer build
    </p>
    <ul class="placeholder-list">
      <li v-for="top in store.index.categories" :key="top.slug">
        <router-link :to="`/${top.slug}`">
          {{ top.display }}
          <span class="placeholder-count">{{
            (store.catsByTop[top.slug] || []).length
          }}</span>
        </router-link>
      </li>
    </ul>
  </main>
</template>
