(function () {
  function bindDropZones() {
    const zones = document.querySelectorAll(".file-drop-zone");

    zones.forEach((zone) => {
      if (zone.dataset.dragBound === "1") return;
      zone.dataset.dragBound = "1";

      let dragCounter = 0;

      zone.addEventListener("dragenter", function (e) {
        e.preventDefault();
        e.stopPropagation();
        dragCounter += 1;
        zone.classList.add("drag-active");
      });

      zone.addEventListener("dragover", function (e) {
        e.preventDefault();
        e.stopPropagation();
        zone.classList.add("drag-active");
      });

      zone.addEventListener("dragleave", function (e) {
        e.preventDefault();
        e.stopPropagation();
        dragCounter -= 1;
        if (dragCounter <= 0) {
          dragCounter = 0;
          zone.classList.remove("drag-active");
        }
      });

      zone.addEventListener("drop", function (e) {
        e.preventDefault();
        e.stopPropagation();
        dragCounter = 0;
        zone.classList.remove("drag-active");
      });
    });
  }

  function initObserver() {
    bindDropZones();

    const observer = new MutationObserver(() => {
      bindDropZones();
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initObserver);
  } else {
    initObserver();
  }
})();