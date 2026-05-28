import { createRouter, createWebHistory } from "vue-router";

import Home from "./views/Home.vue";
import Category from "./views/Category.vue";
import About from "./views/About.vue";
import NotFound from "./views/NotFound.vue";

// Detail is the same view as Category — the pane is an overlay driven by
// route params, not a separately-mounted view.
const routes = [
  { path: "/", name: "home", component: Home },
  { path: "/about", name: "about", component: About },
  { path: "/:top", name: "top", component: Category },
  { path: "/:top/:sub", name: "sub", component: Category },
  { path: "/:top/:sub/:set(\\d+)", name: "set", component: Category },
  {
    path: "/:top/:sub/:set(\\d+)/:slug",
    name: "detail",
    component: Category,
  },
  { path: "/:pathMatch(.*)*", name: "notfound", component: NotFound },
];

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior(to, from) {
    // Opening the detail pane shouldn't reset the page scroll; only
    // navigations that change the underlying view do.
    const isOverlayChange =
      to.params.top === from.params.top &&
      to.params.sub === from.params.sub &&
      (to.name === "detail" || from.name === "detail");
    if (isOverlayChange) return false;
    return { top: 0 };
  },
});
