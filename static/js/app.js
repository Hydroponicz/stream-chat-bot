// Stream Chat Bot — Dashboard JS (SSE consumer + UI updater)

const IS_ADMIN = window.location.pathname === "/admin";
let lastSeq = 0;

// ── SSE connection ─────────────────────────────────────────────────────────────
const evtSource = new EventSource("/events");

evtSource.addEventListener("update", (e) => {
  try {
    const data = JSON.parse(e.data);
    dispatch(data);
  } catch (err) {
    console.error("[SSE] parse error", err);
  }
});

evtSource.onerror = () => {
  console.warn("[SSE] connection lost, retrying in 3s…");
  setTimeout(() => location.reload(), 3000);
};

// ── Dispatcher ────────────────────────────────────────────────────────────────
function dispatch(data) {
  switch (data.type) {
    case "chat":
      appendChat(data);
      updateLeaderboard(data.username);
      break;
    case "trivia_start":
      setTriviaActive(true, data.question, data.answer_preview);
      break;
    case "trivia_stop":
      setTriviaActive(false);
      break;
    case "trivia_win":
      flashTriviaWin(data.username, data.answer);
      break;
    case "points_update":
      refreshLeaderboardEntry(data.username, data.points);
      break;
    case "reset":
      resetUI();
      break;
  }
}

// ── Chat Feed ──────────────────────────────────────────────────────────────────
function appendChat({ platform, username, content, timestamp }) {
  const feedId = IS_ADMIN ? "chat-feed-admin" : "chat-feed";
  const feed = document.getElementById(feedId);
  if (!feed) return;

  const time = timestamp ? new Date(timestamp).toLocaleTimeString() : "";
  const div = document.createElement("div");
  div.className = "chat-msg";
  div.innerHTML =
    `<span class="msg-user ${platform}">${escapeHtml(username)}</span>` +
    `<span class="msg-content">${escapeHtml(content)}</span>` +
    (time ? `<span class="msg-time">${time}</span>` : "");

  feed.appendChild(div);
  feed.scrollTop = feed.scrollHeight;

  // Cap entries at 200
  while (feed.children.length > 200) feed.removeChild(feed.firstChild);
}

// ── Leaderboard ────────────────────────────────────────────────────────────────
function updateLeaderboard(username) {
  // Optimistic: the server will broadcast the actual score
  const lbId = IS_ADMIN ? "leaderboard-list-admin" : "leaderboard-list";
  const lb = document.getElementById(lbId);
  if (!lb) return;
  // Empty state removed once we have data
  const empty = lb.querySelector(".empty-state");
  if (empty) empty.remove();
}

function refreshLeaderboardEntry(username, points) {
  const lbId = IS_ADMIN ? "leaderboard-list-admin" : "leaderboard-list";
  const lb = document.getElementById(lbId);
  if (!lb) return;

  // Find or create entry
  let entry = lb.querySelector(`[data-user="${CSS.escape(username)}"]`);
  if (!entry) {
    entry = document.createElement("div");
    entry.className = "lb-entry";
    entry.setAttribute("data-user", username);
    entry.innerHTML =
      `<span class="lb-rank"></span>` +
      `<span class="lb-user">${escapeHtml(username)}</span>` +
      `<span class="lb-points">${points}</span>`;
    lb.appendChild(entry);
  } else {
    entry.querySelector(".lb-points").textContent = points;
  }

  // Re-sort by points descending
  const entries = Array.from(lb.querySelectorAll(".lb-entry"));
  entries.sort((a, b) => Number(b.querySelector(".lb-points").textContent) - Number(a.querySelector(".lb-points").textContent));
  entries.forEach((el, i) => {
    el.querySelector(".lb-rank").textContent = i + 1;
    lb.appendChild(el);
  });
}

// ── Trivia ─────────────────────────────────────────────────────────────────────
function setTriviaActive(active, question, hint) {
  const statusEl = document.getElementById("trivia-status");
  const questionEl = document.getElementById("trivia-question");
  if (!statusEl) return;

  if (active) {
    statusEl.textContent = "Active";
    statusEl.className = "trivia-status active";
    if (questionEl) questionEl.textContent = question || "";
  } else {
    statusEl.textContent = "Inactive";
    statusEl.className = "trivia-status";
    if (questionEl) questionEl.textContent = "";
  }
}

function flashTriviaWin(username, answer) {
  setTriviaActive(false);
  alert(`🎉 ${username} got the correct answer: "${answer}"`);
}

// ── Admin Controls ─────────────────────────────────────────────────────────────
async function startTrivia() {
  const question = prompt("Enter the trivia question:");
  if (!question) return;
  const answer = prompt("Enter the answer (case-insensitive):");
  if (!answer) return;
  await fetch("/admin/trivia/start", {
    method: "POST",
    body: new URLSearchParams({ question, answer }),
  });
}

async function stopTrivia() {
  await fetch("/admin/trivia/stop", { method: "POST" });
}

async function resetGame() {
  if (!confirm("Reset all messages, leaderboard, and trivia?")) return;
  await fetch("/admin/reset", { method: "POST" });
  resetUI();
}

function resetUI() {
  ["chat-feed", "chat-feed-admin"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = "";
  });
  ["leaderboard-list", "leaderboard-list-admin"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = '<p class="empty-state">No messages yet.</p>';
  });
  setTriviaActive(false);
}

async function givePoints() {
  const userInput = document.getElementById("points-user");
  const amountInput = document.getElementById("points-amount");
  const username = userInput.value.trim();
  const points = parseInt(amountInput.value, 10);
  if (!username || isNaN(points) || points <= 0) {
    alert("Enter a valid username and point amount.");
    return;
  }
  const res = await fetch("/admin/points", {
    method: "POST",
    body: new URLSearchParams({ username, points }),
  });
  if (res.ok) {
    userInput.value = "";
    amountInput.value = "";
  }
}

// ── Util ───────────────────────────────────────────────────────────────────────
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
