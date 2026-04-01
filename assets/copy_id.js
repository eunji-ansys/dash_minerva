console.log("copy_id.js loaded");

function fallbackCopyText(text) {
  const textarea = document.createElement("textarea");
  textarea.value = text;

  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.top = "-9999px";
  textarea.style.left = "-9999px";

  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();

  let success = false;
  try {
    success = document.execCommand("copy");
  } catch (err) {
    console.error("fallback copy failed", err);
    success = false;
  }

  document.body.removeChild(textarea);
  return success;
}

document.addEventListener("click", async function (e) {
  const btn = e.target.closest(".copy-id-btn");
  if (!btn) return;

  console.log("button clicked", btn);

  e.preventDefault();
  e.stopPropagation();

  const text = btn.getAttribute("data-copy-text");
  const originalTitle = btn.getAttribute("data-copy-title") || "Copy Item ID";
  if (!text) return;

  let copied = false;

  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      copied = true;
    } else {
      copied = fallbackCopyText(text);
    }
  } catch (err) {
    console.error("clipboard api failed, trying fallback", err);
    copied = fallbackCopyText(text);
  }

  if (copied) {
    const oldText = btn.textContent;
    btn.textContent = "✓";
    btn.setAttribute("title", "Copied!");

    setTimeout(() => {
      btn.textContent = oldText || "⧉";
      btn.setAttribute("title", originalTitle);
    }, 800);
  } else {
    console.error("copy failed");
    btn.setAttribute("title", "Copy failed");
  }
});