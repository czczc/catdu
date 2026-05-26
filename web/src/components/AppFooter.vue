<script setup>
import { useRoute } from "vue-router";

const route = useRoute();
</script>

<template>
  <footer class="site-footer">
    <div class="site-footer-inner">
      <p class="site-footer-note">
        Avatars and writeups are AI-generated — take the details with a grain of salt.
      </p>
      <nav class="site-footer-links" aria-label="Footer">
        <router-link v-if="route.name !== 'about'" to="/about">About</router-link>
        <span v-else class="site-footer-current">About</span>
        <span class="site-footer-sep">·</span>
        <a
          href="https://github.com/czczc/meowphosis/discussions"
          target="_blank"
          rel="noopener noreferrer"
          >Feedback</a
        >
        <span class="site-footer-sep">·</span>
        <a
          href="https://github.com/czczc/meowphosis"
          target="_blank"
          rel="noopener noreferrer"
          >GitHub</a
        >
      </nav>
    </div>
  </footer>
</template>
