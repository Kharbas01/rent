/* RentFlow Agreement Scanner
 * Lazy-loads OpenCV.js, auto-detects document corners, allows manual adjustment,
 * applies perspective correction, light cleanup, and best-effort auto-orientation.
 */
(function (window, document) {
  const OPENCV_URL = "https://docs.opencv.org/4.10.0/opencv.js";
  const MODAL_ID = "scanReviewModal";
  const MAX_PREVIEW_WIDTH = 980;
  const MAX_PREVIEW_HEIGHT = 620;
  const HANDLE_RADIUS = 12;
  const MIN_DOC_AREA_RATIO = 0.18;

  const state = {
    opencvPromise: null,
    uiReady: false,
    modal: null,
    previewCanvas: null,
    statusEl: null,
    badgeEl: null,
    sourceCanvas: null,
    points: [],
    draggingIndex: -1,
    pointerActive: false,
    previewScale: 1,
    pendingResolve: null,
    detectorAvailable: false,
    lastDetectionSucceeded: false,
    busy: false,
  };

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function distance(a, b) {
    const dx = a.x - b.x;
    const dy = a.y - b.y;
    return Math.sqrt(dx * dx + dy * dy);
  }

  function cloneCanvas(sourceCanvas) {
    const copy = document.createElement("canvas");
    copy.width = sourceCanvas.width;
    copy.height = sourceCanvas.height;
    copy.getContext("2d").drawImage(sourceCanvas, 0, 0);
    return copy;
  }

  function canvasToBlob(canvas, type, quality) {
    return new Promise((resolve, reject) => {
      canvas.toBlob(
        (blob) => {
          if (!blob) {
            reject(new Error("Could not create image blob."));
            return;
          }
          resolve(blob);
        },
        type || "image/jpeg",
        quality == null ? 0.92 : quality
      );
    });
  }

  function defaultQuad(width, height) {
    const mx = Math.round(width * 0.08);
    const my = Math.round(height * 0.08);
    return [
      { x: mx, y: my },
      { x: width - mx, y: my },
      { x: width - mx, y: height - my },
      { x: mx, y: height - my },
    ];
  }

  function orderPoints(points) {
    const pts = points.map((p) => ({ x: p.x, y: p.y }));

    pts.sort((a, b) => a.y - b.y);
    const top = pts.slice(0, 2).sort((a, b) => a.x - b.x);
    const bottom = pts.slice(2, 4).sort((a, b) => a.x - b.x);

    return [
      top[0],       // top-left
      top[1],       // top-right
      bottom[1],    // bottom-right
      bottom[0],    // bottom-left
    ];
  }

  function normalizePoints(points, width, height) {
    return orderPoints(points).map((point) => ({
      x: clamp(point.x, 0, width - 1),
      y: clamp(point.y, 0, height - 1),
    }));
  }

  function injectStyles() {
    if (document.getElementById("agreement-scanner-styles")) return;

    const style = document.createElement("style");
    style.id = "agreement-scanner-styles";
    style.textContent = `
      .scanner-modal-card {
        width: min(1100px, calc(100vw - 32px));
      }

      .scanner-shell {
        display: grid;
        gap: 14px;
      }

      .scanner-stage {
        position: relative;
        border-radius: var(--radius-lg);
        border: 1px solid var(--border);
        overflow: hidden;
        background: rgba(6, 10, 20, 0.74);
        min-height: 320px;
      }

      .scanner-preview {
        width: 100%;
        display: block;
        touch-action: none;
        cursor: crosshair;
      }

      .scanner-meta {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        flex-wrap: wrap;
      }

      .scanner-status {
        margin: 0;
        color: var(--muted, rgba(255,255,255,0.72));
        font-size: 0.95rem;
      }

      .scanner-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        border-radius: 999px;
        padding: 6px 10px;
        border: 1px solid var(--border);
        background: rgba(255,255,255,0.08);
        color: var(--text, #fff);
        font-size: 0.84rem;
        white-space: nowrap;
      }

      .scanner-badge.success {
        border-color: rgba(70, 190, 120, 0.38);
        background: rgba(70, 190, 120, 0.14);
      }

      .scanner-badge.warn {
        border-color: rgba(255, 186, 73, 0.38);
        background: rgba(255, 186, 73, 0.14);
      }

      .scanner-toolbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        flex-wrap: wrap;
      }

      .scanner-toolbar-left,
      .scanner-toolbar-right {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
      }

      .scanner-note {
        margin: 0;
        padding: 12px 14px;
        border: 1px solid var(--border);
        border-radius: var(--radius-lg);
        background: rgba(255,255,255,0.04);
        color: var(--muted, rgba(255,255,255,0.72));
        font-size: 0.92rem;
        line-height: 1.45;
      }

      .scanner-note strong {
        color: var(--text, #fff);
      }

      @media (max-width: 720px) {
        .scanner-toolbar,
        .scanner-toolbar-left,
        .scanner-toolbar-right,
        .scanner-meta {
          align-items: stretch;
        }

        .scanner-toolbar-left,
        .scanner-toolbar-right {
          width: 100%;
        }

        .scanner-toolbar-left .btn,
        .scanner-toolbar-right .btn {
          flex: 1 1 auto;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function ensureUi() {
    if (state.uiReady) return;

    injectStyles();

    const wrapper = document.createElement("div");
    wrapper.innerHTML = `
      <div class="modal" id="${MODAL_ID}" hidden>
        <div class="modal-backdrop" data-scan-close></div>
        <div class="modal-card glass wide scanner-modal-card" role="dialog" aria-modal="true" aria-labelledby="scanReviewTitle">
          <div class="modal-head">
            <h2 id="scanReviewTitle">Review scanned page</h2>
            <button class="icon-btn" type="button" data-scan-close aria-label="Close">&times;</button>
          </div>
          <div class="modal-body scanner-shell">
            <div class="scanner-meta">
              <p class="scanner-status" id="scannerStatus">Detecting document edges…</p>
              <span class="scanner-badge" id="scannerBadge">Preparing scanner</span>
            </div>

            <div class="scanner-stage">
              <canvas id="scannerPreviewCanvas" class="scanner-preview"></canvas>
            </div>

            <div class="scanner-toolbar">
              <div class="scanner-toolbar-left">
                <button type="button" class="btn btn-soft btn-sm" id="scannerDetectBtn">Detect again</button>
                <button type="button" class="btn btn-ghost btn-sm" id="scannerResetBtn">Reset corners</button>
              </div>
              <div class="scanner-toolbar-right">
                <button type="button" class="btn btn-ghost btn-sm" id="scannerKeepRawBtn">Keep raw capture</button>
                <button type="button" class="btn btn-primary btn-sm" id="scannerApplyBtn">Use corrected page</button>
              </div>
            </div>

            <p class="scanner-note">
              <strong>Manual fallback:</strong> drag the four corner handles to match the page edges exactly,
              then click <strong>Use corrected page</strong>. If this page is already flat or detection is wrong,
              choose <strong>Keep raw capture</strong>.
            </p>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(wrapper.firstElementChild);

    state.modal = document.getElementById(MODAL_ID);
    state.previewCanvas = document.getElementById("scannerPreviewCanvas");
    state.statusEl = document.getElementById("scannerStatus");
    state.badgeEl = document.getElementById("scannerBadge");

    state.previewCanvas.addEventListener("pointerdown", onPointerDown);
    state.previewCanvas.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointercancel", onPointerUp);

    document.getElementById("scannerDetectBtn").addEventListener("click", rerunDetection);
    document.getElementById("scannerResetBtn").addEventListener("click", resetCorners);
    document.getElementById("scannerKeepRawBtn").addEventListener("click", keepRawCapture);
    document.getElementById("scannerApplyBtn").addEventListener("click", applyCorrection);
    state.modal.querySelectorAll("[data-scan-close]").forEach((el) => {
      el.addEventListener("click", cancelReview);
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && state.modal && !state.modal.hidden) {
        cancelReview();
      }
    });

    state.uiReady = true;
  }

  function openModal() {
    if (!state.modal) return;
    state.modal.hidden = false;
  }

  function closeModal() {
    if (!state.modal) return;
    state.modal.hidden = true;
  }

  function setStatus(message, badgeLabel, badgeClass) {
    if (state.statusEl) state.statusEl.textContent = message;
    if (state.badgeEl) {
      state.badgeEl.textContent = badgeLabel || "";
      state.badgeEl.className = "scanner-badge" + (badgeClass ? " " + badgeClass : "");
    }
  }

  function canUseCv() {
    return !!(window.cv && typeof window.cv.imread === "function");
  }

  function ensureReady() {
    ensureUi();

    if (canUseCv()) {
      state.detectorAvailable = true;
      return Promise.resolve(window.cv);
    }

    if (state.opencvPromise) return state.opencvPromise;

    state.opencvPromise = new Promise((resolve, reject) => {
      let timeoutId = null;

      function cleanup() {
        if (timeoutId) clearTimeout(timeoutId);
      }

      function resolveIfReady() {
        if (canUseCv()) {
          state.detectorAvailable = true;
          cleanup();
          resolve(window.cv);
          return true;
        }
        return false;
      }

      if (resolveIfReady()) return;

      const previousModule = window.Module || {};
      window.Module = Object.assign({}, previousModule, {
        onRuntimeInitialized: function () {
          if (typeof previousModule.onRuntimeInitialized === "function") {
            previousModule.onRuntimeInitialized();
          }
          resolveIfReady();
        },
      });

      let existing = document.querySelector('script[data-opencv-js="true"]');
      if (!existing) {
        existing = document.createElement("script");
        existing.src = OPENCV_URL;
        existing.async = true;
        existing.defer = true;
        existing.dataset.opencvJs = "true";
        existing.onerror = function () {
          cleanup();
          state.detectorAvailable = false;
          state.opencvPromise = null;
          reject(new Error("Could not load OpenCV.js."));
        };
        document.head.appendChild(existing);
      }

      timeoutId = window.setTimeout(() => {
        if (!resolveIfReady()) {
          state.detectorAvailable = false;
          state.opencvPromise = null;
          reject(new Error("OpenCV.js initialization timed out."));
        }
      }, 20000);
    });

    return state.opencvPromise;
  }

  function drawPreview() {
    if (!state.previewCanvas || !state.sourceCanvas || !state.points.length) return;

    const source = state.sourceCanvas;
    const scale = Math.min(
      1,
      MAX_PREVIEW_WIDTH / source.width,
      MAX_PREVIEW_HEIGHT / source.height
    );
    state.previewScale = scale;

    const canvas = state.previewCanvas;
    canvas.width = Math.round(source.width * scale);
    canvas.height = Math.round(source.height * scale);

    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(source, 0, 0, canvas.width, canvas.height);

    const scaled = state.points.map((p) => ({
      x: p.x * scale,
      y: p.y * scale,
    }));

    ctx.save();
    ctx.fillStyle = "rgba(0, 0, 0, 0.44)";
    ctx.beginPath();
    ctx.rect(0, 0, canvas.width, canvas.height);
    ctx.moveTo(scaled[0].x, scaled[0].y);
    for (let i = 1; i < scaled.length; i += 1) {
      ctx.lineTo(scaled[i].x, scaled[i].y);
    }
    ctx.closePath();
    ctx.fill("evenodd");
    ctx.restore();

    ctx.save();
    ctx.strokeStyle = "#56d6ff";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(scaled[0].x, scaled[0].y);
    for (let i = 1; i < scaled.length; i += 1) {
      ctx.lineTo(scaled[i].x, scaled[i].y);
    }
    ctx.closePath();
    ctx.stroke();

    scaled.forEach((point, index) => {
      ctx.fillStyle = "#56d6ff";
      ctx.beginPath();
      ctx.arc(point.x, point.y, HANDLE_RADIUS, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = "#08101f";
      ctx.beginPath();
      ctx.arc(point.x, point.y, HANDLE_RADIUS * 0.48, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = "#ffffff";
      ctx.font = "12px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(String(index + 1), point.x, point.y);
    });
    ctx.restore();
  }

  function eventToSourcePoint(event) {
    const rect = state.previewCanvas.getBoundingClientRect();
    const x = clamp(event.clientX - rect.left, 0, rect.width);
    const y = clamp(event.clientY - rect.top, 0, rect.height);
    return {
      x: x / state.previewScale,
      y: y / state.previewScale,
    };
  }

  function nearestHandleIndex(sourcePoint) {
    let bestIndex = -1;
    let bestDistance = Infinity;
    const threshold = 26 / state.previewScale;

    state.points.forEach((point, index) => {
      const d = distance(point, sourcePoint);
      if (d < bestDistance && d <= threshold) {
        bestDistance = d;
        bestIndex = index;
      }
    });

    return bestIndex;
  }

  function onPointerDown(event) {
    if (!state.sourceCanvas || !state.points.length) return;
    const sourcePoint = eventToSourcePoint(event);
    const index = nearestHandleIndex(sourcePoint);
    if (index === -1) return;

    state.draggingIndex = index;
    state.pointerActive = true;
    state.previewCanvas.setPointerCapture(event.pointerId);
    event.preventDefault();
  }

  function onPointerMove(event) {
    if (!state.pointerActive || state.draggingIndex === -1 || !state.sourceCanvas) return;

    const sourcePoint = eventToSourcePoint(event);
    state.points[state.draggingIndex] = {
      x: clamp(sourcePoint.x, 0, state.sourceCanvas.width - 1),
      y: clamp(sourcePoint.y, 0, state.sourceCanvas.height - 1),
    };
    drawPreview();
    event.preventDefault();
  }

  function onPointerUp(event) {
    if (!state.pointerActive) return;
    if (state.previewCanvas && state.previewCanvas.hasPointerCapture && event.pointerId != null) {
      try {
        state.previewCanvas.releasePointerCapture(event.pointerId);
      } catch (e) {
        /* no-op */
      }
    }
    state.pointerActive = false;
    state.draggingIndex = -1;
  }

  function extractQuadPoints(mat) {
    const pts = [];
    for (let i = 0; i < 4; i += 1) {
      pts.push({
        x: mat.data32S[i * 2],
        y: mat.data32S[i * 2 + 1],
      });
    }
    return pts;
  }

  function detectDocument(sourceCanvas) {
    if (!canUseCv()) return null;

    const cv = window.cv;
    const src = cv.imread(sourceCanvas);
    const maxSide = Math.max(src.cols, src.rows);
    const scale = maxSide > 1400 ? 1400 / maxSide : 1;

    const working = new cv.Mat();
    if (scale !== 1) {
      cv.resize(
        src,
        working,
        new cv.Size(Math.round(src.cols * scale), Math.round(src.rows * scale)),
        0,
        0,
        cv.INTER_AREA
      );
    } else {
      src.copyTo(working);
    }

    const gray = new cv.Mat();
    const blurred = new cv.Mat();
    const edges = new cv.Mat();
    const kernel = cv.getStructuringElement(cv.MORPH_RECT, new cv.Size(5, 5));
    const contours = new cv.MatVector();
    const hierarchy = new cv.Mat();

    let best = null;
    let bestArea = 0;

    try {
      cv.cvtColor(working, gray, cv.COLOR_RGBA2GRAY);
      cv.GaussianBlur(gray, blurred, new cv.Size(5, 5), 0, 0, cv.BORDER_DEFAULT);
      cv.Canny(blurred, edges, 60, 180);
      cv.dilate(edges, edges, kernel);
      cv.morphologyEx(edges, edges, cv.MORPH_CLOSE, kernel);

      cv.findContours(edges, contours, hierarchy, cv.RETR_LIST, cv.CHAIN_APPROX_SIMPLE);
      const minArea = working.cols * working.rows * MIN_DOC_AREA_RATIO;

      for (let i = 0; i < contours.size(); i += 1) {
        const contour = contours.get(i);
        const approx = new cv.Mat();
        try {
          const perimeter = cv.arcLength(contour, true);
          cv.approxPolyDP(contour, approx, 0.02 * perimeter, true);

          const area = Math.abs(cv.contourArea(approx));
          if (
            approx.rows === 4 &&
            area > minArea &&
            area > bestArea &&
            cv.isContourConvex(approx)
          ) {
            const quad = extractQuadPoints(approx);
            best = quad;
            bestArea = area;
          }
        } finally {
          contour.delete();
          approx.delete();
        }
      }

      if (!best) return null;

      const normalized = normalizePoints(
        best.map((point) => ({
          x: point.x / scale,
          y: point.y / scale,
        })),
        sourceCanvas.width,
        sourceCanvas.height
      );

      const topWidth = distance(normalized[0], normalized[1]);
      const bottomWidth = distance(normalized[3], normalized[2]);
      const leftHeight = distance(normalized[0], normalized[3]);
      const rightHeight = distance(normalized[1], normalized[2]);

      if (
        Math.min(topWidth, bottomWidth, leftHeight, rightHeight) <
        Math.min(sourceCanvas.width, sourceCanvas.height) * 0.18
      ) {
        return null;
      }

      return normalized;
    } finally {
      src.delete();
      working.delete();
      gray.delete();
      blurred.delete();
      edges.delete();
      kernel.delete();
      contours.delete();
      hierarchy.delete();
    }
  }

  function rotateCanvas(sourceCanvas, degrees) {
    const normalized = ((degrees % 360) + 360) % 360;
    if (normalized === 0) return sourceCanvas;

    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");

    if (normalized === 90 || normalized === 270) {
      canvas.width = sourceCanvas.height;
      canvas.height = sourceCanvas.width;
    } else {
      canvas.width = sourceCanvas.width;
      canvas.height = sourceCanvas.height;
    }

    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.rotate((normalized * Math.PI) / 180);
    ctx.drawImage(sourceCanvas, -sourceCanvas.width / 2, -sourceCanvas.height / 2);

    return canvas;
  }

  function estimateDarkRatio(imageData, startY, endY) {
    const data = imageData.data;
    const width = imageData.width;
    const clampedStart = clamp(Math.floor(startY), 0, imageData.height);
    const clampedEnd = clamp(Math.floor(endY), 0, imageData.height);
    let dark = 0;
    let total = 0;

    for (let y = clampedStart; y < clampedEnd; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const idx = (y * width + x) * 4;
        const r = data[idx];
        const g = data[idx + 1];
        const b = data[idx + 2];
        const luminance = 0.299 * r + 0.587 * g + 0.114 * b;
        if (luminance < 180) dark += 1;
        total += 1;
      }
    }

    return total ? dark / total : 0;
  }

  function autoOrientCanvas(sourceCanvas) {
    let working = sourceCanvas;

    // Most agreement pages are portrait; rotate if the corrected page is clearly landscape.
    if (working.width > working.height * 1.08) {
      working = rotateCanvas(working, 90);
    }

    // Best-effort 180° flip heuristic based on top/bottom darkness balance.
    // This is intentionally conservative to avoid rotating already-correct pages unnecessarily.
    const ctx = working.getContext("2d");
    const sampleHeight = Math.min(working.height, 900);
    const sampleWidth = Math.min(working.width, 700);
    const probeCanvas = document.createElement("canvas");
    probeCanvas.width = sampleWidth;
    probeCanvas.height = sampleHeight;
    probeCanvas.getContext("2d").drawImage(working, 0, 0, sampleWidth, sampleHeight);
    const imageData = probeCanvas.getContext("2d").getImageData(0, 0, sampleWidth, sampleHeight);
    const band = Math.max(24, Math.floor(sampleHeight * 0.14));
    const topDark = estimateDarkRatio(imageData, 0, band);
    const bottomDark = estimateDarkRatio(imageData, sampleHeight - band, sampleHeight);

    if (topDark > bottomDark * 1.42 && Math.abs(topDark - bottomDark) > 0.02) {
      working = rotateCanvas(working, 180);
    }

    // If we created a new canvas, return it; otherwise return original.
    return working;
  }

  function warpFromPoints(sourceCanvas, points) {
    if (!canUseCv()) {
      throw new Error("OpenCV.js is not available for perspective correction.");
    }

    const cv = window.cv;
    const ordered = normalizePoints(points, sourceCanvas.width, sourceCanvas.height);

    const topWidth = distance(ordered[0], ordered[1]);
    const bottomWidth = distance(ordered[3], ordered[2]);
    const leftHeight = distance(ordered[0], ordered[3]);
    const rightHeight = distance(ordered[1], ordered[2]);

    const destWidth = Math.max(1, Math.round(Math.max(topWidth, bottomWidth)));
    const destHeight = Math.max(1, Math.round(Math.max(leftHeight, rightHeight)));

    const src = cv.imread(sourceCanvas);
    const srcTri = cv.matFromArray(4, 1, cv.CV_32FC2, [
      ordered[0].x, ordered[0].y,
      ordered[1].x, ordered[1].y,
      ordered[2].x, ordered[2].y,
      ordered[3].x, ordered[3].y,
    ]);
    const dstTri = cv.matFromArray(4, 1, cv.CV_32FC2, [
      0, 0,
      destWidth - 1, 0,
      destWidth - 1, destHeight - 1,
      0, destHeight - 1,
    ]);

    const matrix = cv.getPerspectiveTransform(srcTri, dstTri);
    const warped = new cv.Mat();
    const rgb = new cv.Mat();
    const cleaned = new cv.Mat();
    const adjusted = new cv.Mat();
    const rgba = new cv.Mat();

    try {
      cv.warpPerspective(
        src,
        warped,
        matrix,
        new cv.Size(destWidth, destHeight),
        cv.INTER_LINEAR,
        cv.BORDER_REPLICATE,
        new cv.Scalar()
      );

      cv.cvtColor(warped, rgb, cv.COLOR_RGBA2RGB);
      cv.bilateralFilter(rgb, cleaned, 5, 35, 35, cv.BORDER_DEFAULT);
      cv.convertScaleAbs(cleaned, adjusted, 1.08, 5);
      cv.cvtColor(adjusted, rgba, cv.COLOR_RGB2RGBA);

      const outCanvas = document.createElement("canvas");
      outCanvas.width = rgba.cols;
      outCanvas.height = rgba.rows;
      cv.imshow(outCanvas, rgba);

      return autoOrientCanvas(outCanvas);
    } finally {
      src.delete();
      srcTri.delete();
      dstTri.delete();
      matrix.delete();
      warped.delete();
      rgb.delete();
      cleaned.delete();
      adjusted.delete();
      rgba.delete();
    }
  }

  async function rerunDetection() {
    if (!state.sourceCanvas || state.busy) return;

    state.busy = true;
    setStatus("Re-running edge detection…", "Detecting", "warn");

    try {
      await ensureReady();
      const detected = detectDocument(state.sourceCanvas);
      if (detected) {
        state.points = detected;
        state.lastDetectionSucceeded = true;
        drawPreview();
        setStatus(
          "Auto-detected the document edges. Drag any corner if needed, then confirm.",
          "Auto-detected",
          "success"
        );
      } else {
        state.points = defaultQuad(state.sourceCanvas.width, state.sourceCanvas.height);
        state.lastDetectionSucceeded = false;
        drawPreview();
        setStatus(
          "Detection could not find a clean page outline. Adjust the corners manually or keep the raw capture.",
          "Manual review",
          "warn"
        );
      }
    } catch (error) {
      state.lastDetectionSucceeded = false;
      state.points = defaultQuad(state.sourceCanvas.width, state.sourceCanvas.height);
      drawPreview();
      setStatus(
        "Scanner enhancement is unavailable right now. You can still keep the raw capture.",
        "Raw fallback",
        "warn"
      );
    } finally {
      state.busy = false;
    }
  }

  function resetCorners() {
    if (!state.sourceCanvas) return;
    state.points = defaultQuad(state.sourceCanvas.width, state.sourceCanvas.height);
    state.lastDetectionSucceeded = false;
    drawPreview();
    setStatus(
      "Corners reset. Drag them onto the page edges, then confirm.",
      "Manual review",
      "warn"
    );
  }

  function finalize(result) {
    const resolve = state.pendingResolve;
    state.pendingResolve = null;
    closeModal();
    state.sourceCanvas = null;
    state.points = [];
    state.draggingIndex = -1;
    state.pointerActive = false;
    state.busy = false;
    if (resolve) resolve(result);
  }

  function cancelReview() {
    finalize(null);
  }

  async function keepRawCapture() {
    if (!state.sourceCanvas) {
      finalize(null);
      return;
    }

    const blob = await canvasToBlob(state.sourceCanvas, "image/jpeg", 0.92);
    finalize({
      blob: blob,
      corrected: false,
      mode: "raw",
    });
  }

  async function applyCorrection() {
    if (!state.sourceCanvas || state.busy) return;

    if (!canUseCv()) {
      keepRawCapture();
      return;
    }

    state.busy = true;
    setStatus("Applying perspective correction…", "Processing", "warn");

    try {
      const correctedCanvas = warpFromPoints(state.sourceCanvas, state.points);
      const blob = await canvasToBlob(correctedCanvas, "image/jpeg", 0.92);
      finalize({
        blob: blob,
        corrected: true,
        mode: state.lastDetectionSucceeded ? "auto" : "manual",
      });
    } catch (error) {
      setStatus(
        "Correction failed for this capture. You can keep the raw image instead.",
        "Raw fallback",
        "warn"
      );
      state.busy = false;
    }
  }

  async function reviewCapture(options) {
    ensureUi();

    if (state.pendingResolve) {
      state.pendingResolve(null);
      state.pendingResolve = null;
    }

    const sourceCanvas = options && options.sourceCanvas ? options.sourceCanvas : null;
    if (!sourceCanvas) {
      throw new Error("reviewCapture requires a sourceCanvas.");
    }

    state.sourceCanvas = cloneCanvas(sourceCanvas);
    state.points = defaultQuad(state.sourceCanvas.width, state.sourceCanvas.height);
    state.lastDetectionSucceeded = false;
    state.draggingIndex = -1;
    state.pointerActive = false;
    state.busy = false;

    drawPreview();
    setStatus("Preparing scanner…", "Loading", "warn");
    openModal();

    try {
      await ensureReady();
      const detected = detectDocument(state.sourceCanvas);
      if (detected) {
        state.points = detected;
        state.lastDetectionSucceeded = true;
        drawPreview();
        setStatus(
          "Auto-detected the document edges. Drag any corner if needed, then confirm.",
          "Auto-detected",
          "success"
        );
      } else {
        state.points = defaultQuad(state.sourceCanvas.width, state.sourceCanvas.height);
        drawPreview();
        setStatus(
          "Detection could not find a clean page outline. Adjust the corners manually or keep the raw capture.",
          "Manual review",
          "warn"
        );
      }
    } catch (error) {
      state.points = defaultQuad(state.sourceCanvas.width, state.sourceCanvas.height);
      drawPreview();
      setStatus(
        "Scanner enhancement is unavailable right now. You can still keep the raw capture.",
        "Raw fallback",
        "warn"
      );
    }

    return new Promise((resolve) => {
      state.pendingResolve = resolve;
    });
  }

  window.AgreementScanner = {
    ensureReady: ensureReady,
    reviewCapture: reviewCapture,
    close: closeModal,
  };
})(window, document);
