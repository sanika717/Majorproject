/**
 * UrbanPulse - Intelligence Assistant (frontend only, Phase 4B)
 * No LLM, API or generated answers. Suggested questions only fill the
 * (disabled) input to show the intended interaction.
 * TODO (later phase): send messages to the assistant backend and render replies.
 */
document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("chat-input");
  const form = document.getElementById("chat-form");
  const box = document.getElementById("chat-messages");
  if (!input || !form || !box) return;
  form.addEventListener("submit", (e) => e.preventDefault());
  document.querySelectorAll("#chat-suggestions [data-q]").forEach(btn => {
    btn.addEventListener("click", () => {
      input.value = btn.dataset.q;
      const note = document.createElement("div");
      note.className = "chat-msg assistant";
      note.textContent = "The assistant backend isn't connected yet, so this question can't be answered at the moment.";
      if (!box.querySelector("[data-pending]")) { note.dataset.pending = "1"; box.appendChild(note); }
      box.scrollTop = box.scrollHeight;
    });
  });
});
