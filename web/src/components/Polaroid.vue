<script setup>
import { imageUrl } from "../catalog.js";

const props = defineProps({
  cat: { type: Object, required: true },
  size: { type: Number, default: 120 },
  rotate: { type: Number, default: 0 },
});
</script>

<template>
  <div
    class="polaroid"
    :style="{ transform: `rotate(${props.rotate}deg)` }"
    aria-hidden="false"
  >
    <div
      class="polaroid-window"
      :style="{ width: props.size + 'px', height: props.size + 'px' }"
    >
      <img
        :src="imageUrl(props.cat.image_path)"
        :alt="props.cat.english_name"
        :width="props.size"
        :height="props.size"
        loading="lazy"
        decoding="async"
      />
    </div>
  </div>
</template>
