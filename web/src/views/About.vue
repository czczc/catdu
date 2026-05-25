<script setup>
import { totalCats, totalCategories } from "../catalog.js";
</script>

<template>
  <main class="shell">
    <section class="masthead">
      <div class="masthead-row">
        <h1 class="headline headline-home">About Meowphosis</h1>
        <span class="meta-caps">HOME / ABOUT</span>
      </div>
      <p class="lede">
        A personal, non-commercial fan project — cute cats reimagined as
        gods, places, characters, and particles. {{ totalCats }} cats across
        {{ totalCategories }} categories, growing slowly.
      </p>
    </section>

    <div class="rule" />

    <article class="about-body">
      <section>
        <h2>About the avatars</h2>
        <p>
          Every cat avatar on this site is generated with image AI from a
          short, themed prompt — for example, "a chibi watercolor cat dressed
          as Zeus, with a small lightning bolt and scepter, cream background."
          The companion writeup (iconography, summary, wiki link) is
          assembled by a language model and then reviewed by hand. Despite
          the review pass, some details may be slightly off, miscredited, or
          oversimplified. Read with discretion; don't cite the site as a
          source for anything that matters.
        </p>
      </section>

      <section>
        <h2>About the source material</h2>
        <p>
          Categories are organized around concepts that already exist in the
          world: mythological figures, places, scientific ideas, characters
          from games and other media. The cats are reinterpretations, not
          reproductions — no character art is copied, only the
          <em>idea</em> of a character is reimagined as a cat with thematic
          accessories.
        </p>
        <p>
          All names, characters, trademarks, and other intellectual property
          referenced on this site remain the property of their respective
          owners. The cat artworks themselves are fan-created, transformative
          works made for personal, non-commercial enjoyment. They are not
          endorsed, sponsored, or affiliated with any of the original
          creators or rights-holders.
        </p>
      </section>

      <section>
        <h2>If you're a rights-holder</h2>
        <p>
          If you own the rights to something depicted here and would prefer
          it not be reimagined as a cat on this page, please open an issue at
          <a
            href="https://github.com/czczc/meowphosis/issues/new?title=Takedown%20request&labels=takedown"
            target="_blank"
            rel="noopener noreferrer"
            >github.com/czczc/meowphosis/issues</a
          >. The catalog is small and easy to update — anything you'd like
          removed will be taken down promptly, no questions asked.
        </p>
      </section>

      <section>
        <h2>About AI-generated content and copyright</h2>
        <p>
          Under current US guidance, content produced purely by generative AI
          is not eligible for copyright. The cats on this site fall under
          that bucket. You're welcome to view, share, and enjoy them; please
          don't sell them or pass them off as your own original art.
        </p>
      </section>
    </article>

    <footer class="home-footer">
      <p>
        <router-link to="/">← Back to the catalog</router-link>
      </p>
    </footer>
  </main>
</template>
