import { ref } from "vue";

// Routes:
//   #/                                  → home
//   #/<top>/<sub>                       → sub-category (set tabs + grid)
//   #/<top>/<sub>/<set>/<slug>          → logo detail
// Anything else falls back to home.

function parseHash() {
  const raw = window.location.hash.replace(/^#\/?/, "").replace(/\/$/, "");
  if (!raw) return { name: "home" };
  const parts = raw.split("/").filter(Boolean);
  if (parts.length === 2) {
    return { name: "sub", top: parts[0], sub: parts[1] };
  }
  if (parts.length === 4) {
    return {
      name: "logo",
      top: parts[0],
      sub: parts[1],
      set: parseInt(parts[2], 10),
      slug: parts[3],
    };
  }
  return { name: "home" };
}

export const route = ref(parseHash());

window.addEventListener("hashchange", () => {
  route.value = parseHash();
  window.scrollTo({ top: 0 });
});

export function href(target) {
  if (target.name === "home") return "#/";
  if (target.name === "sub") return `#/${target.top}/${target.sub}`;
  if (target.name === "logo")
    return `#/${target.top}/${target.sub}/${target.set}/${target.slug}`;
  return "#/";
}
