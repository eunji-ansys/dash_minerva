(function () {
  function initImageViewer() {
    const stage = document.getElementById("viewer-image-stage");
    const img = document.getElementById("viewer-image");
    if (!stage || !img) return;

    if (stage.dataset.viewerBound === "1") return;
    stage.dataset.viewerBound = "1";

    let scale = 1;
    const minScale = 0.2;
    const maxScale = 8;
    const zoomStep = 0.12;

    let isDragging = false;
    let startX = 0;
    let startY = 0;
    let startScrollLeft = 0;
    let startScrollTop = 0;

    function clamp(value, min, max) {
      return Math.max(min, Math.min(max, value));
    }

    function applyScale() {
        img.style.transform = `scale(${scale})`;

        if (scale <= 1) {
            img.style.maxWidth = "100%";
            img.style.maxHeight = "100%";
        } else {
            img.style.maxWidth = "none";
            img.style.maxHeight = "none";
        }

        stage.dataset.scale = String(scale);
        }

    function zoomAt(clientX, clientY, direction) {
      const rect = stage.getBoundingClientRect();

      const offsetX = clientX - rect.left + stage.scrollLeft;
      const offsetY = clientY - rect.top + stage.scrollTop;

      const prevScale = scale;
      const factor = direction > 0 ? (1 + zoomStep) : (1 - zoomStep);
      scale = clamp(scale * factor, minScale, maxScale);

      if (scale === prevScale) return;

      applyScale();

      const ratio = scale / prevScale;
      stage.scrollLeft = offsetX * ratio - (clientX - rect.left);
      stage.scrollTop = offsetY * ratio - (clientY - rect.top);
    }

    stage.addEventListener(
      "wheel",
      function (e) {
        e.preventDefault();
        zoomAt(e.clientX, e.clientY, e.deltaY < 0 ? 1 : -1);
      },
      { passive: false }
    );

    stage.addEventListener("mousedown", function (e) {
      if (e.button !== 0) return;
      isDragging = true;
      stage.classList.add("is-dragging");
      startX = e.clientX;
      startY = e.clientY;
      startScrollLeft = stage.scrollLeft;
      startScrollTop = stage.scrollTop;
    });

    window.addEventListener("mousemove", function (e) {
      if (!isDragging) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      stage.scrollLeft = startScrollLeft - dx;
      stage.scrollTop = startScrollTop - dy;
    });

    window.addEventListener("mouseup", function () {
      if (!isDragging) return;
      isDragging = false;
      stage.classList.remove("is-dragging");
    });

    stage.addEventListener("mouseleave", function () {
      if (!isDragging) return;
      isDragging = false;
      stage.classList.remove("is-dragging");
    });

    img.addEventListener("load", function () {
      scale = 1;
      applyScale();
      stage.scrollLeft = 0;
      stage.scrollTop = 0;
    });

    applyScale();
  }

  function tryInit() {
    initImageViewer();
    requestAnimationFrame(initImageViewer);
    setTimeout(initImageViewer, 100);
    setTimeout(initImageViewer, 300);
  }

  document.addEventListener("DOMContentLoaded", tryInit);
  document.addEventListener("mouseup", tryInit);

  const observer = new MutationObserver(() => {
    if (document.getElementById("viewer-image-stage")) {
      tryInit();
    }
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
  });
})();