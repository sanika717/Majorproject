/**
 * UrbanPulse - Public Complaints (frontend only, Phase 4B)
 * No backend, storage or API. Submission is intentionally disabled.
 * TODO (later phase): POST the form to a complaints service; GET "My Complaints".
 */
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("complaint-form");
  if (!form) return;
  const file = document.getElementById("c-file");
  const name = document.getElementById("c-file-name");
  if (file && name) file.addEventListener("change", () => { name.textContent = file.files[0] ? file.files[0].name : ""; });
  form.addEventListener("submit", (e) => e.preventDefault()); // backend pending
});
