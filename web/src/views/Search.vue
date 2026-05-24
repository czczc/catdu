<script setup>
import { ref, computed, watch } from "vue";
import { loadAllShards, imageUrl } from "../catalog.js";
import { href } from "../router.js";

const props = defineProps({ query: { type: String, required: true } });

const shards = ref(null);

watch(
  () => props.query,
  async (q) => {
    if (q && !shards.value) {
      shards.value = await loadAllShards();
    }
  },
  { immediate: true },
);

function highlight(text, q) {
  if (!q) return text;
  const i = text.toLowerCase().indexOf(q.toLowerCase());
  if (i < 0) return text;
  return [
    text.slice(0, i),
    { mark: text.slice(i, i + q.length) },
    text.slice(i + q.length),
  ];
}

const results = computed(() => {
  if (!shards.value || !props.query) return null;
  const q = props.query.trim().toLowerCase();
  if (!q) return null;
  const out = [];
  for (const shard of shards.value) {
    for (const set of shard.sets) {
      for (const logo of set.logos) {
        const matches = {
          name: logo.english_name.toLowerCase().includes(q),
          chinese: logo.chinese_name?.toLowerCase().includes(q),
          icon: (logo.iconography || []).find((ic) =>
            ic.toLowerCase().includes(q),
          ),
        };
        if (matches.name || matches.chinese || matches.icon) {
          out.push({
            logo,
            shard,
            set,
            matches,
          });
        }
      }
    }
  }
  return out;
});
</script>

<template>
  <div class="search-results">
    <div class="section-head">
      <h2>Search</h2>
      <span class="crumb">“{{ query }}”</span>
    </div>
    <p v-if="!shards" class="loading">Loading the whole catalog…</p>
    <template v-else>
      <p class="results-meta" v-if="results">
        {{ results.length }} match{{ results.length === 1 ? "" : "es" }} for
        “{{ query }}”
      </p>
      <hr class="double-rule" />

      <ul v-if="results && results.length" class="logo-grid">
        <li v-for="r in results" :key="r.logo.id">
          <a
            class="logo-card"
            :href="href({
              name: 'logo',
              top: r.shard.top.slug,
              sub: r.shard.sub.slug,
              set: r.set.set_number,
              slug: r.logo.english_slug,
            })"
          >
            <img
              :src="imageUrl(r.logo.image_path)"
              :alt="r.logo.english_name"
              loading="lazy"
            />
            <span class="num"
              >{{ r.shard.sub.display }} {{ r.shard.top.display }} · Set
              {{ r.set.set_number }}</span
            >
            <span class="name">
              <template
                v-for="(part, i) in [highlight(r.logo.english_name, query)].flat()"
                :key="i"
              >
                <mark v-if="part?.mark">{{ part.mark }}</mark>
                <template v-else>{{ part }}</template>
              </template>
            </span>
            <div class="chips" v-if="r.matches.icon">
              <span class="chip">
                <template
                  v-for="(part, i) in [highlight(r.matches.icon, query)].flat()"
                  :key="i"
                >
                  <mark v-if="part?.mark">{{ part.mark }}</mark>
                  <template v-else>{{ part }}</template>
                </template>
              </span>
            </div>
          </a>
        </li>
      </ul>
      <p v-else-if="results" class="loading">
        Nothing matches. Try “lightning”, “shield”, “shell”…
      </p>
    </template>
  </div>
</template>
