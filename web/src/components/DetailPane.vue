<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch, nextTick } from "vue";
import { useRouter } from "vue-router";
import { store } from "../catalog.js";
import Polaroid from "./Polaroid.vue";

const props = defineProps({
  cat: { type: Object, required: true },
});

const router = useRouter();
const paneEl = ref(null);
const previousFocus = ref(null);

const relatedCats = computed(() => {
  // Up to 6 cats from the same sub, alphabetical neighbors of `props.cat`,
  // wrapping at edges, excluding self.
  const peers = (store.catsByTop[props.cat.top] || [])
    .filter((c) => c.sub === props.cat.sub)
    .sort((a, b) => a.english_name.localeCompare(b.english_name));
  if (peers.length <= 1) return [];
  const idx = peers.findIndex(
    (c) =>
      c.set_number === props.cat.set_number &&
      c.english_slug === props.cat.english_slug,
  );
  if (idx === -1) return peers.slice(0, 6);
  const n = peers.length;
  const want = Math.min(6, n - 1);
  const before = Math.floor(want / 2);
  const start = ((idx - before) % n + n) % n;
  const out = [];
  for (let i = 1; out.length < want; i++) {
    const at = (start + i - 1) % n;
    if (at === idx) continue;
    out.push(peers[at]);
  }
  return out;
});

const palette = computed(() => props.cat.palette || []);

function closePane() {
  router.replace({
    name: props.cat.sub ? "sub" : "top",
    params: props.cat.sub
      ? { top: props.cat.top, sub: props.cat.sub }
      : { top: props.cat.top },
  });
}

function onKeydown(e) {
  if (e.key === "Escape") {
    e.preventDefault();
    closePane();
  } else if (e.key === "Tab" && paneEl.value) {
    // Focus trap.
    const focusables = paneEl.value.querySelectorAll(
      'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    if (focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }
}

onMounted(() => {
  previousFocus.value = document.activeElement;
  document.body.classList.add("detail-open");
  document.addEventListener("keydown", onKeydown);
  nextTick(() => {
    paneEl.value?.querySelector(".pane-x")?.focus();
  });
});

onBeforeUnmount(() => {
  document.body.classList.remove("detail-open");
  document.removeEventListener("keydown", onKeydown);
  if (previousFocus.value && typeof previousFocus.value.focus === "function") {
    previousFocus.value.focus();
  }
});

// When user switches to a related cat (cat prop changes), reset pane scroll.
watch(
  () => props.cat.english_slug,
  () => {
    if (paneEl.value) paneEl.value.scrollTop = 0;
  },
);
</script>

<template>
  <teleport to="body">
    <transition name="pane-scrim">
      <div class="pane-scrim" @click="closePane" />
    </transition>
    <transition name="detail-pane">
      <aside
        class="detail-pane"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="`pane-name-${cat.english_slug}`"
        ref="paneEl"
      >
        <header class="pane-hdr">
          <nav class="pane-crumb" aria-label="Breadcrumb">
            <router-link :to="`/${cat.top}`">{{ cat.top_display }}</router-link>
            <span class="crumb-sep">/</span>
            <router-link :to="`/${cat.top}/${cat.sub}`">{{
              cat.sub_display
            }}</router-link>
          </nav>
          <button
            type="button"
            class="pane-x"
            @click="closePane"
            aria-label="Close detail"
          >
            ×
          </button>
        </header>

        <div class="pane-hero">
          <div class="pane-polaroid">
            <Polaroid :cat="cat" :size="300" :rotate="-2" />
          </div>
        </div>

        <section class="pane-titles">
          <h1 class="pane-name" :id="`pane-name-${cat.english_slug}`">
            {{ cat.english_name }}
          </h1>
          <p v-if="cat.summary" class="pane-tagline">{{ cat.summary }}</p>
        </section>

        <div class="pane-stats">
          <div class="stat">
            <span class="stat-k">Cell</span>
            <span class="stat-v-mono">
              #{{ String(cat.source_cell ?? 0).padStart(3, "0") }}
            </span>
          </div>
          <div class="stat">
            <span class="stat-k">Series</span>
            <span class="stat-v">
              {{ cat.sub_display
              }}<template v-if="(cat.set_number ?? 1) > 1">
                · Set {{ cat.set_number }}</template
              >
            </span>
          </div>
        </div>

        <section v-if="cat.iconography?.length" class="pane-sect">
          <header class="pane-sect-hd">
            <span class="pane-sect-label">Iconography</span>
            <span class="pane-sect-rule" />
          </header>
          <div class="tag-row">
            <span v-for="ic in cat.iconography" :key="ic" class="tag">{{
              ic
            }}</span>
          </div>
        </section>

        <section v-if="palette.length" class="pane-sect">
          <header class="pane-sect-hd">
            <span class="pane-sect-label">Palette</span>
            <span class="pane-sect-rule" />
          </header>
          <div class="palette-row">
            <div v-for="hex in palette" :key="hex" class="swatch">
              <span class="swatch-chip" :style="{ background: hex }" />
              <span class="swatch-hex">{{ hex.toUpperCase() }}</span>
            </div>
          </div>
        </section>

        <section v-if="relatedCats.length" class="pane-sect">
          <header class="pane-sect-hd">
            <span class="pane-sect-label"
              >Also in {{ cat.sub_display }}</span
            >
            <span class="pane-sect-rule" />
          </header>
          <div class="also-row">
            <router-link
              v-for="other in relatedCats"
              :key="`${other.set_number}/${other.english_slug}`"
              :to="`/${other.top}/${other.sub}/${other.set_number}/${other.english_slug}`"
              class="also-thumb"
              replace
            >
              <Polaroid :cat="other" :size="90" />
              <p class="also-name">{{ other.english_name }}</p>
            </router-link>
          </div>
        </section>

        <footer class="pane-foot">
          <span>end of file</span>
          <span class="pane-foot-diamond" aria-hidden="true" />
        </footer>
      </aside>
    </transition>
  </teleport>
</template>
