const treeEl = document.getElementById("tree");
const statusEl = document.getElementById("status");
const topTpl = document.getElementById("top-template");
const subTpl = document.getElementById("sub-template");

async function load() {
  const data = await fetch("/api/visibility").then((r) => r.json());
  render(data.categories);
}

function render(categories) {
  treeEl.innerHTML = "";
  for (const top of categories) {
    const node = topTpl.content.cloneNode(true);
    const section = node.querySelector(".top");
    section.dataset.top = top.slug;
    if (top.hidden) section.classList.add("is-hidden");

    const topToggle = node.querySelector(".top-toggle");
    topToggle.checked = !top.hidden;
    topToggle.addEventListener("change", () =>
      toggle({ scope: "top", top: top.slug, hidden: !topToggle.checked }, section),
    );

    node.querySelector(".top-slug").textContent = top.slug;
    node.querySelector(".top-display").textContent = top.display;
    const subTotal = top.sub_categories.reduce((n, s) => n + s.logo_count, 0);
    node.querySelector(".top-count").textContent = `${subTotal} cats`;

    const subs = node.querySelector(".subs");
    for (const sub of top.sub_categories) {
      const subNode = subTpl.content.cloneNode(true);
      const label = subNode.querySelector("label");
      label.dataset.sub = sub.slug;
      if (sub.hidden) label.classList.add("is-hidden");

      const subToggle = subNode.querySelector(".sub-toggle");
      subToggle.checked = !sub.hidden;
      subToggle.disabled = top.hidden;
      subToggle.addEventListener("change", () =>
        toggle(
          { scope: "sub", top: top.slug, sub: sub.slug, hidden: !subToggle.checked },
          label,
        ),
      );

      subNode.querySelector(".sub-slug").textContent = sub.slug;
      subNode.querySelector(".sub-display").textContent = sub.display;
      subNode.querySelector(".sub-count").textContent = `${sub.logo_count} cats`;

      subs.appendChild(subNode);
    }

    treeEl.appendChild(node);
  }
}

async function toggle(payload, el) {
  el.classList.add("pending");
  setStatus("Saving…", "");
  try {
    const res = await fetch("/api/visibility/toggle", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await res.json();
    if (!res.ok || !body.ok) {
      setStatus(`Error: ${body.stderr || body.detail || res.statusText}`, "err");
      return;
    }
    const label = payload.scope === "top" ? payload.top : `${payload.top}/${payload.sub}`;
    setStatus(`${payload.hidden ? "Hid" : "Showed"} ${label} · catalog rebuilt.`, "ok");
    await load();
  } catch (e) {
    setStatus(`Error: ${e.message}`, "err");
  } finally {
    el.classList.remove("pending");
  }
}

function setStatus(msg, kind) {
  statusEl.hidden = false;
  statusEl.textContent = msg;
  statusEl.className = `status ${kind}`;
}

load();
