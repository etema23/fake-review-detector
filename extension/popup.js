// Popup: shows whether the local server is running and lets you check any review manually.

const $ = (id) => document.getElementById(id);

function send(type, payload) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type, payload }, (res) => {
      if (chrome.runtime.lastError) return reject(new Error(chrome.runtime.lastError.message));
      if (!res || !res.ok) return reject(new Error(res ? res.error : "No response"));
      resolve(res.data);
    });
  });
}

send("health")
  .then(() => {
    $("status").textContent = "● Server connected";
    $("status").className = "status ok";
  })
  .catch(() => {
    $("status").textContent = "● Server offline (run: uvicorn server:app --port 8000)";
    $("status").className = "status off";
  });

$("check").addEventListener("click", async () => {
  const review = $("review").value.trim();
  if (!review) return;

  $("check").disabled = true;
  $("check").textContent = "Checking...";
  $("result").hidden = true;

  try {
    const { probs } = await send("score", { reviews: [review] });
    const prob = probs[0];
    const pct = Math.round(prob * 100);
    const fake = prob > 0.5;

    $("verdict").textContent = fake ? `⚠ ${pct}% likely fake` : `✓ ${100 - pct}% likely real`;
    $("verdict").className = fake ? "verdict fake" : "verdict real";
    // Bar shows confidence in the displayed verdict, so it matches the label
    $("fill").style.width = (fake ? pct : 100 - pct) + "%";
    $("fill").className = fake ? "fake" : "real";
    $("explanation").textContent = "Getting explanation...";
    $("result").hidden = false;

    const { explanation } = await send("explain", { review, prob });
    $("explanation").textContent = explanation;
  } catch (err) {
    $("verdict").textContent = "Couldn't reach the server";
    $("verdict").className = "verdict";
    $("explanation").textContent = "";
    $("result").hidden = false;
  }

  $("check").disabled = false;
  $("check").textContent = "Check";
});
