// Content script: finds reviews on Amazon product pages, scores them through the
// local server, and adds a badge above each one.

// Each review is wrapped in data-hook="review". The text element inside it differs
// between Amazon's newer and older layouts, so check both. (Class names on the new
// layout are hashed, e.g. _Y3Itd_contain-rich-content_2IORW, so they aren't reliable.)
const TEXT_SELECTORS = [
  '[data-hook="reviewRichContentContainer"]', // current layout
  '[data-hook="review-body"]', // older layout
  '[data-hook="review-collapsed"]',
].join(", ");

const seen = new WeakSet(); // reviews that already have a badge

function findReviews() {
  return [...document.querySelectorAll('[data-hook="review"]')]
    .map((review) => review.querySelector(TEXT_SELECTORS))
    .filter(Boolean);
}

function send(type, payload) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type, payload }, (res) => {
      if (chrome.runtime.lastError) return reject(new Error(chrome.runtime.lastError.message));
      if (!res || !res.ok) return reject(new Error(res ? res.error : "No response"));
      resolve(res.data);
    });
  });
}

function makeBadge(text, cls) {
  const badge = document.createElement("div");
  badge.className = "frd-badge " + cls;
  badge.textContent = text;
  return badge;
}

// Explanations are only fetched on click, since each one costs an API call
function addWhyButton(badge, text, prob) {
  const btn = document.createElement("button");
  btn.className = "frd-why";
  btn.textContent = "Why?";

  btn.addEventListener("click", async (e) => {
    e.preventDefault();
    e.stopPropagation();
    btn.disabled = true;
    btn.textContent = "...";
    try {
      const { explanation } = await send("explain", { review: text, prob });
      const box = document.createElement("div");
      box.className = "frd-explain";
      box.textContent = explanation;
      badge.after(box);
      btn.remove();
    } catch (err) {
      btn.disabled = false;
      btn.textContent = "Why? (retry)";
    }
  });

  badge.append(btn);
}

function showResult(badge, text, prob) {
  const pct = Math.round(prob * 100);
  if (prob > 0.5) {
    badge.className = "frd-badge " + (prob > 0.7 ? "frd-high" : "frd-mid");
    badge.textContent = `⚠ ${pct}% likely fake`;
    addWhyButton(badge, text, prob);
  } else {
    badge.className = "frd-badge frd-low";
    badge.textContent = `✓ ${100 - pct}% likely real`;
  }
}

async function scan() {
  const reviews = findReviews()
    .filter((el) => !seen.has(el))
    .map((el) => ({ el, text: el.innerText.trim() }))
    .filter((r) => r.text);

  if (reviews.length === 0) return;
  console.log(`[fake review detector] found ${reviews.length} reviews`);
  reviews.forEach((r) => seen.add(r.el));

  const badges = reviews.map((r) => {
    const badge = makeBadge("Checking...", "frd-loading");
    r.el.before(badge);
    return badge;
  });

  try {
    // Score the whole page in one request (one embed call instead of one per review)
    const { probs } = await send("score", { reviews: reviews.map((r) => r.text) });
    reviews.forEach((r, i) => showResult(badges[i], r.text, probs[i]));
  } catch (err) {
    badges.forEach((b) => {
      b.className = "frd-badge frd-error";
      b.textContent = "Server not running";
    });
  }
}

// Amazon loads more reviews without a full page reload, so rescan when the DOM changes.
// Debounced so a burst of mutations only triggers one scan.
let timer;
new MutationObserver(() => {
  clearTimeout(timer);
  timer = setTimeout(scan, 800);
}).observe(document.body, { childList: true, subtree: true });

scan();
