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

const peerCats = computed(() =>
  (store.catsByTop[props.cat.top] || [])
    .filter((c) => c.sub === props.cat.sub)
    .sort((a, b) => a.english_name.localeCompare(b.english_name)),
);

const currentIdx = computed(() =>
  peerCats.value.findIndex(
    (c) =>
      c.set_number === props.cat.set_number &&
      c.english_slug === props.cat.english_slug,
  ),
);

const prevCat = computed(() => {
  const peers = peerCats.value;
  if (peers.length <= 1 || currentIdx.value === -1) return null;
  return peers[(currentIdx.value - 1 + peers.length) % peers.length];
});

const nextCat = computed(() => {
  const peers = peerCats.value;
  if (peers.length <= 1 || currentIdx.value === -1) return null;
  return peers[(currentIdx.value + 1) % peers.length];
});

const relatedCats = computed(() => {
  // Up to 6 alphabetical neighbors of `props.cat`, wrapping, excluding self.
  const peers = peerCats.value;
  if (peers.length <= 1) return [];
  const idx = currentIdx.value;
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

function goTo(target) {
  if (!target) return;
  router.replace(
    `/${target.top}/${target.sub}/${target.set_number}/${target.english_slug}`,
  );
}

const palette = computed(() => props.cat.palette || []);

// Lowest set in this cat's sub — the default set, which lives at the bare sub
// URL (matching the set-switcher convention in Category.vue).
const lowestSet = computed(() => {
  const inSub = (store.catsByTop[props.cat.top] || []).filter(
    (c) => c.sub === props.cat.sub,
  );
  return inSub.length ? Math.min(...inSub.map((c) => c.set_number)) : null;
});

function closePane() {
  // Return to the list scoped to this logo's set, not just the category.
  if (!props.cat.sub) {
    router.replace({ name: "top", params: { top: props.cat.top } });
  } else if (props.cat.set_number === lowestSet.value) {
    router.replace({
      name: "sub",
      params: { top: props.cat.top, sub: props.cat.sub },
    });
  } else {
    router.replace({
      name: "set",
      params: {
        top: props.cat.top,
        sub: props.cat.sub,
        set: String(props.cat.set_number),
      },
    });
  }
}

function onKeydown(e) {
  if (e.key === "Escape") {
    e.preventDefault();
    closePane();
  } else if (e.key === "ArrowLeft" && prevCat.value) {
    e.preventDefault();
    goTo(prevCat.value);
  } else if (e.key === "ArrowRight" && nextCat.value) {
    e.preventDefault();
    goTo(nextCat.value);
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
      <div
        class="pane-scrim"
        @click="closePane"
        aria-hidden="true"
      />
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
          <button
            v-if="prevCat"
            type="button"
            class="pane-nav pane-nav-prev"
            @click="goTo(prevCat)"
            :aria-label="`Previous: ${prevCat.english_name}`"
            :title="prevCat.english_name"
          >
            <span aria-hidden="true">‹</span>
          </button>
          <div class="pane-polaroid">
            <Polaroid :cat="cat" :size="280" />
          </div>
          <button
            v-if="nextCat"
            type="button"
            class="pane-nav pane-nav-next"
            @click="goTo(nextCat)"
            :aria-label="`Next: ${nextCat.english_name}`"
            :title="nextCat.english_name"
          >
            <span aria-hidden="true">›</span>
          </button>
        </div>

        <section class="pane-titles">
          <h1 class="pane-name" :id="`pane-name-${cat.english_slug}`">
            {{ cat.english_name }}
          </h1>
          <p v-if="cat.chinese_name" class="pane-chinese">{{ cat.chinese_name }}</p>
          <p v-if="cat.summary" class="pane-tagline">{{ cat.summary }}</p>
          <a
            v-if="cat.wiki_url"
            class="pane-wiki"
            :href="cat.wiki_url"
            target="_blank"
            rel="noopener noreferrer"
          >
            Read on {{ cat.wiki_url.includes("wikipedia.org") ? "Wikipedia" : "the wiki" }}
            <span aria-hidden="true">↗</span>
          </a>
        </section>

        <div class="pane-stats">
          <div class="stat">
            <span class="stat-k">Cell</span>
            <span class="stat-v-mono">
              #{{ String(cat.source_cell ?? 0).padStart(3, "0") }}
            </span>
          </div>
          <div class="stat">
            <span class="stat-k">Category</span>
            <span class="stat-v">{{ cat.sub_display }}</span>
          </div>
          <div class="stat">
            <span class="stat-k">Set</span>
            <span class="stat-v">{{
              cat.set_display || `Set ${cat.set_number}`
            }}</span>
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

      </aside>
    </transition>
  </teleport>
</template>
