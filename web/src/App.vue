<script setup>
import { ref, computed } from "vue";
import { route, href } from "./router.js";
import Home from "./views/Home.vue";
import SubCategory from "./views/SubCategory.vue";
import LogoDetail from "./views/LogoDetail.vue";
import Search from "./views/Search.vue";

const query = ref("");

const view = computed(() => {
  if (query.value.trim()) return { name: "search" };
  return route.value;
});
</script>

<template>
  <div class="site">
    <header class="site-header">
      <div class="site-header-inner">
        <a class="wordmark" :href="href({ name: 'home' })"
          >meowphosis<span class="ornament">✦</span></a
        >
        <span class="tagline">a catalog of cat logos</span>
        <div class="search-wrap">
          <input
            class="search"
            type="search"
            v-model="query"
            placeholder="Search iconography, name…"
            aria-label="Search"
          />
        </div>
      </div>
    </header>

    <main class="site-main">
      <Search v-if="view.name === 'search'" :query="query" />
      <Home v-else-if="view.name === 'home'" />
      <SubCategory v-else-if="view.name === 'sub'" />
      <LogoDetail v-else-if="view.name === 'logo'" />
    </main>

    <footer class="site-footer">
      meowphosis <span class="ornament">✦</span> cats all the way down
    </footer>
  </div>
</template>
