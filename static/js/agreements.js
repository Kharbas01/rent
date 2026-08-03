/* Agreement management: list, filters, upload/camera capture, Google Drive actions. */
(function () {
  const state = {
    items: [],
    properties: [],
    tenants: [],
    search: "",
    status: "all",
    propertyId: "",
    tenantId: "",
    // New-agreement form state
    source: "upload",
    selectedFile: null,
    pages: [], // [{ blob, url, rotation, scanMode }]
    stream: null,
    scannerReady: false,
    scannerLoadingPromise: null,
    captureInProgress: false,
  };

  document.addEventListener("DOMContentLoaded", () => {
    ["agreementModal", "replaceModal"].forEach(UI.bindModalClose);

    document.getElementById("addAgreementBtn").addEventListener("click", () => openForm());
    document.getElementById("agreementForm").addEventListener("submit", save);
    document.getElementById("replaceForm").addEventListener("submit", saveReplace);

    bindSourceTabs();
    bindUploadPanel();
    bindCameraPanel();
    bindReplacePanel();

    document.getElementById("agreementSearch").addEventListener(
      "input",
      UI.debounce((e) => {
        state.search = e.target.value.trim();
        load();
      }, 320)
    );

    document.getElementById("agreementStatusFilter").addEventListener("change", (e) => {
      state.status = e.target.value;
      load();
    });

    document.getElementById("agreementPropertyFilter").addEventListener("change", (e) => {
      state.propertyId = e.target.value;
      load();
    });

    document.getElementById("agreementTenantFilter").addEventListener("change", (e) => {
      state.tenantId = e.target.value;
      load();
    });

    document.getElementById("agreementClearFilters").addEventListener("click", () => {
      state.search = "";
      state.status = "all";
      state.propertyId = "";
      state.tenantId = "";
      document.getElementById("agreementSearch").value = "";
      document.getElementById("agreementStatusFilter").value = "all";
      document.getElementById("agreementPropertyFilter").value = "";
      document.getElementById("agreementTenantFilter").value = "";
      load();
    });

    // Stop the camera whenever the modal closes, however it closes.
    document.getElementById("agreementModal").addEventListener("click", (e) => {
      if (e.target.matches("[data-close]")) stopCamera();
    });

    document.addEventListener("profileready", init, { once: true });
  });

  async function init() {
    await Promise.all([loadProperties(), loadTenants()]);
    load();
  }

  async function loadProperties() {
    try {
      const data = await API.get("/api/properties");
      state.properties = data.items;
      const options = state.properties
        .map((p) => '<option value="' + p.id + '">' + UI.escapeHtml(p.name) + "</option>")
        .join("");
      document.getElementById("agreementPropertyFilter").innerHTML =
        '<option value="">All properties</option>' + options;
      document.getElementById("agreementProperty").innerHTML =
        '<option value="">— Not linked —</option>' + options;
    } catch (error) {
      UI.toast("Could not load properties: " + error.message, "error");
    }
  }

  async function loadTenants() {
    try {
      const data = await API.get("/api/tenants");
      state.tenants = data.items;
      const options = state.tenants
        .map((t) => '<option value="' + t.id + '">' + UI.escapeHtml(t.name) + "</option>")
        .join("");
      document.getElementById("agreementTenantFilter").innerHTML =
        '<option value="">All tenants</option>' + options;
      document.getElementById("agreementTenant").innerHTML =
        '<option value="">— Not linked —</option>' + options;
    } catch (error) {
      UI.toast("Could not load tenants: " + error.message, "error");
    }
  }

  async function load() {
    const container = document.getElementById("agreementTable");
    UI.showLoader(container);
    try {
      const data = await API.get("/api/agreements", {
        search: state.search,
        status: state.status,
        property_id: state.propertyId,
        tenant_id: state.tenantId,
      });
      state.items = data.items;
      render(container, data.items);
    } catch (error) {
      UI.toast(error.message, "error");
      UI.emptyState(container, {
        icon: "&#9888;",
        title: "Could not load agreements",
        message: error.message,
      });
    }
  }

  function statusBadge(status) {
    const map = {
      Active: "badge-success",
      "Expiring Soon": "badge-warn",
      Expired: "badge-danger",
    };
    return '<span class="badge ' + (map[status] || "badge-muted") + '">' + UI.escapeHtml(status) + "</span>";
  }

  function formatSize(bytes) {
    const n = Number(bytes || 0);
    if (n >= 1024 * 1024) return (n / (1024 * 1024)).toFixed(1) + " MB";
    if (n >= 1024) return (n / 1024).toFixed(0) + " KB";
    return n + " B";
  }

  function render(container, items) {
    if (!items.length) {
      UI.emptyState(container, {
        icon: "&#128196;",
        title:
          state.search || state.status !== "all" || state.propertyId || state.tenantId
            ? "No matching agreements"
            : "No agreements yet",
        message:
          state.search || state.status !== "all" || state.propertyId || state.tenantId
            ? "Try a different search term or clear the filters."
            : "Upload a signed agreement or scan one with your camera.",
        actionId: "emptyAddAgreement",
        actionLabel: "+ New agreement",
      });
      const button = document.getElementById("emptyAddAgreement");
      if (button) button.addEventListener("click", () => openForm());
      return;
    }

    container.innerHTML =
      "<table><thead><tr><th>Document</th><th>Property</th><th>Tenant</th><th>Period</th>" +
      "<th>Size</th><th>Pages</th><th>Status</th>" +
      '<th class="text-right">Actions</th></tr></thead><tbody>' +
      items
        .map((a) => {
          const property = a.properties ? a.properties.name : "—";
          const tenant = a.tenants ? a.tenants.name : "—";
          const period =
            a.agreement_start || a.agreement_end
              ? UI.formatDate(a.agreement_start) + " → " + UI.formatDate(a.agreement_end)
              : "—";

          return (
            "<tr>" +
            '<td><span class="cell-title">&#128196; ' +
            UI.escapeHtml(a.file_name) +
            "</span>" +
            (a.original_file_name && a.original_file_name !== a.file_name
              ? '<span class="cell-sub">was: ' + UI.escapeHtml(a.original_file_name) + "</span>"
              : "") +
            "</td>" +
            "<td>" + UI.escapeHtml(property) + "</td>" +
            "<td>" + UI.escapeHtml(tenant) + "</td>" +
            '<td><span class="cell-sub">' + period + "</span></td>" +
            "<td>" + formatSize(a.file_size) + "</td>" +
            "<td>" + (a.page_count || 1) + "</td>" +
            "<td>" + statusBadge(a.status) + "</td>" +
            '<td><div class="cell-actions">' +
            (a.drive_link
              ? '<a class="btn btn-ghost btn-sm" href="' +
                a.drive_link +
                '" target="_blank" rel="noopener">Open</a>'
              : "") +
            '<button class="btn btn-ghost btn-sm" data-download="' + a.id + '">Download</button>' +
            '<button class="btn btn-ghost btn-sm" data-replace="' + a.id + '">Replace</button>' +
            '<button class="btn btn-ghost btn-sm" data-edit="' + a.id + '">Edit</button>' +
            '<button class="btn btn-danger btn-sm" data-delete="' + a.id + '">Delete</button>' +
            "</div></td></tr>"
          );
        })
        .join("") +
      "</tbody></table>";

    container.querySelectorAll("[data-download]").forEach((b) =>
      b.addEventListener("click", () => downloadAgreement(b.dataset.download))
    );
    container.querySelectorAll("[data-replace]").forEach((b) =>
      b.addEventListener("click", () => openReplace(b.dataset.replace))
    );
    container.querySelectorAll("[data-edit]").forEach((b) =>
      b.addEventListener("click", () => openForm(b.dataset.edit))
    );
    container.querySelectorAll("[data-delete]").forEach((b) =>
      b.addEventListener("click", () => remove(b.dataset.delete))
    );
  }

  async function downloadAgreement(id) {
    try {
      const response = await fetch("/api/agreements/" + id + "/download", {
        credentials: "same-origin",
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || "Could not download this file.");
      }
      const blob = await response.blob();
      const item = state.items.find((a) => a.id === id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = item ? item.file_name : "agreement";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      UI.toast(error.message, "error");
    }
  }

  async function remove(id) {
    if (!UI.confirmAction("Delete this agreement and its file on Google Drive? This cannot be undone.")) {
      return;
    }
    try {
      await API.del("/api/agreements/" + id);
      UI.toast("Agreement deleted.", "success");
      load();
    } catch (error) {
      UI.toast(error.message, "error");
    }
  }

  /* ---------------- Source tabs (upload vs. camera) ---------------- */
  function bindSourceTabs() {
    const tabs = document.getElementById("agreementSourceTabs");
    tabs.addEventListener("click", (event) => {
      const tab = event.target.closest(".tab");
      if (!tab) return;

      tabs.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      state.source = tab.dataset.source;

      document.getElementById("uploadPanel").hidden = state.source !== "upload";
      document.getElementById("cameraPanel").hidden = state.source !== "camera";

      if (state.source === "camera") {
        warmScanner();
      } else {
        stopCamera();
      }
    });
  }

  /* ---------------- Upload panel: drag & drop + file picker ---------------- */
  const MAX_MB = 20;
  const ALLOWED_EXT = [".pdf", ".jpg", ".jpeg", ".png"];

  function validateClientFile(file) {
    const name = file.name.toLowerCase();
    const okExt = ALLOWED_EXT.some((ext) => name.endsWith(ext));
    if (!okExt) return "Only PDF, JPG and PNG files are supported.";
    if (file.size > MAX_MB * 1024 * 1024) {
      return "File is too large. Maximum allowed size is " + MAX_MB + " MB.";
    }
    if (file.size === 0) return "That file appears to be empty.";
    return null;
  }

  function bindUploadPanel() {
    const zone = document.getElementById("dropZone");
    const input = document.getElementById("fileInput");

    document.getElementById("browseFileBtn").addEventListener("click", () => input.click());
    input.addEventListener("change", () => {
      if (input.files[0]) setSelectedFile(input.files[0]);
    });

    ["dragenter", "dragover"].forEach((evt) =>
      zone.addEventListener(evt, (e) => {
        e.preventDefault();
        zone.classList.add("dropzone-active");
      })
    );

    ["dragleave", "drop"].forEach((evt) =>
      zone.addEventListener(evt, (e) => {
        e.preventDefault();
        zone.classList.remove("dropzone-active");
      })
    );

    zone.addEventListener("drop", (e) => {
      const file = e.dataTransfer.files && e.dataTransfer.files[0];
      if (file) setSelectedFile(file);
    });

    document.getElementById("fileChipRemove").addEventListener("click", () => {
      state.selectedFile = null;
      input.value = "";
      document.getElementById("fileChip").hidden = true;
      document.getElementById("dropZone").hidden = false;
    });
  }

  function setSelectedFile(file) {
    const error = validateClientFile(file);
    if (error) return UI.toast(error, "error");
    state.selectedFile = file;
    document.getElementById("fileChipName").textContent = file.name;
    document.getElementById("fileChipMeta").textContent = formatSize(file.size);
    document.getElementById("fileChip").hidden = false;
    document.getElementById("dropZone").hidden = true;
  }

  /* ---------------- Camera panel: capture multiple pages ---------------- */
  function bindCameraPanel() {
    document.getElementById("startCameraBtn").addEventListener("click", startCamera);
    document.getElementById("captureBtn").addEventListener("click", capturePage);
  }

  async function warmScanner() {
    const hint = document.getElementById("cameraHint");
    if (!window.AgreementScanner) {
      hint.textContent = "Scanner helper is unavailable — you can still capture raw pages.";
      return false;
    }

    if (state.scannerReady) {
      if (!state.stream) {
        hint.textContent = "Scanner ready — start the camera to capture pages.";
      }
      return true;
    }

    if (!state.scannerLoadingPromise) {
      hint.textContent = "Loading document scanner…";
      state.scannerLoadingPromise = window.AgreementScanner
        .ensureReady()
        .then(() => {
          state.scannerReady = true;
          if (!state.stream) {
            hint.textContent = "Scanner ready — start the camera to capture pages.";
          }
          return true;
        })
        .catch((error) => {
          console.warn("Agreement scanner warmup failed:", error);
          state.scannerReady = false;
          hint.textContent =
            "Scanner enhancement could not load — captures still work, and you can keep raw photos.";
          return false;
        })
        .finally(() => {
          state.scannerLoadingPromise = null;
        });
    }

    return state.scannerLoadingPromise;
  }

  async function startCamera() {
    const hint = document.getElementById("cameraHint");
    const warmupPromise = warmScanner();

    try {
      state.stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "environment",
        },
        audio: false,
      });

      const video = document.getElementById("cameraVideo");
      video.srcObject = state.stream;
      document.getElementById("captureBtn").disabled = false;

      const scannerOk = await warmupPromise.catch(() => false);
      hint.textContent = scannerOk
        ? "Camera ready — capture a page, review the detected corners, then confirm."
        : "Camera ready — scanner enhancement is unavailable, but raw capture still works.";
    } catch (error) {
      UI.toast("Could not access the camera: " + error.message, "error");
    }
  }

  function stopCamera() {
    if (state.stream) {
      state.stream.getTracks().forEach((track) => track.stop());
      state.stream = null;
    }

    const video = document.getElementById("cameraVideo");
    if (video) video.srcObject = null;

    const captureBtn = document.getElementById("captureBtn");
    if (captureBtn) captureBtn.disabled = true;

    if (window.AgreementScanner && typeof window.AgreementScanner.close === "function") {
      window.AgreementScanner.close();
    }
  }

  function canvasToBlob(canvas, type, quality) {
    return new Promise((resolve, reject) => {
      canvas.toBlob(
        (blob) => {
          if (!blob) {
            reject(new Error("Could not create an image from the camera capture."));
            return;
          }
          resolve(blob);
        },
        type || "image/jpeg",
        quality == null ? 0.92 : quality
      );
    });
  }

  async function capturePage() {
    if (state.captureInProgress) return;

    const video = document.getElementById("cameraVideo");
    const canvas = document.getElementById("cameraCanvas");
    const captureBtn = document.getElementById("captureBtn");
    const hint = document.getElementById("cameraHint");

    if (!video.videoWidth) {
      return UI.toast("Camera is still starting up — try again in a moment.", "error");
    }

    state.captureInProgress = true;
    captureBtn.disabled = true;
    hint.textContent = "Processing capture…";

    try {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);

      const rawBlob = await canvasToBlob(canvas, "image/jpeg", 0.92);
      let result = {
        blob: rawBlob,
        corrected: false,
        mode: "raw",
      };

      if (window.AgreementScanner && typeof window.AgreementScanner.reviewCapture === "function") {
        const reviewed = await window.AgreementScanner.reviewCapture({
          sourceCanvas: canvas,
          rawBlob: rawBlob,
        });

        if (!reviewed) {
          hint.textContent = "Capture cancelled — line up the page and try again.";
          return;
        }

        result = reviewed;
      }

      const url = URL.createObjectURL(result.blob);
      state.pages.push({
        blob: result.blob,
        url: url,
        rotation: 0,
        scanMode: result.mode || "raw",
      });

      renderPageStrip();

      if (result.corrected) {
        hint.textContent =
          result.mode === "manual"
            ? "Page added with manual corner adjustment."
            : "Page added with auto-scan correction.";
      } else {
        hint.textContent = "Raw page added.";
      }
    } catch (error) {
      UI.toast(error.message || "Could not capture this page.", "error");
      hint.textContent = "Capture failed — try again.";
    } finally {
      state.captureInProgress = false;
      captureBtn.disabled = !state.stream;
    }
  }

  function renderPageStrip() {
    const strip = document.getElementById("pageStrip");
    if (!state.pages.length) {
      strip.innerHTML = "";
      return;
    }

    strip.innerHTML = state.pages
      .map((page, i) => {
        const scanLabel =
          page.scanMode === "auto"
            ? '<span class="cell-sub">Auto-corrected</span>'
            : page.scanMode === "manual"
            ? '<span class="cell-sub">Manual crop</span>'
            : "";

        return (
          '<div class="page-thumb">' +
          '<img src="' + page.url + '" style="transform:rotate(' + page.rotation + 'deg);" />' +
          '<span class="page-thumb-num">' + (i + 1) + "</span>" +
          '<div class="page-thumb-actions">' +
          '<button type="button" class="icon-btn" data-rotate="' + i + '" title="Rotate">&#8635;</button>' +
          '<button type="button" class="icon-btn" data-up="' + i + '" title="Move up">&#8593;</button>' +
          '<button type="button" class="icon-btn" data-down="' + i + '" title="Move down">&#8595;</button>' +
          '<button type="button" class="icon-btn" data-remove="' + i + '" title="Remove">&times;</button>' +
          "</div>" +
          scanLabel +
          "</div>"
        );
      })
      .join("");

    strip.querySelectorAll("[data-rotate]").forEach((b) =>
      b.addEventListener("click", () => rotatePage(Number(b.dataset.rotate)))
    );
    strip.querySelectorAll("[data-up]").forEach((b) =>
      b.addEventListener("click", () => movePage(Number(b.dataset.up), -1))
    );
    strip.querySelectorAll("[data-down]").forEach((b) =>
      b.addEventListener("click", () => movePage(Number(b.dataset.down), 1))
    );
    strip.querySelectorAll("[data-remove]").forEach((b) =>
      b.addEventListener("click", () => removePage(Number(b.dataset.remove)))
    );
  }

  function rotatePage(index) {
    const page = state.pages[index];
    const newRotation = (page.rotation + 90) % 360;

    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      const rotated90 = newRotation === 90 || newRotation === 270;
      canvas.width = rotated90 ? img.height : img.width;
      canvas.height = rotated90 ? img.width : img.height;
      const ctx = canvas.getContext("2d");
      ctx.translate(canvas.width / 2, canvas.height / 2);
      ctx.rotate((newRotation * Math.PI) / 180 - (page.rotation * Math.PI) / 180);
      ctx.drawImage(img, -img.width / 2, -img.height / 2);
      canvas.toBlob((blob) => {
        URL.revokeObjectURL(page.url);
        state.pages[index] = {
          blob: blob,
          url: URL.createObjectURL(blob),
          rotation: 0,
          scanMode: page.scanMode,
        };
        renderPageStrip();
      }, "image/jpeg", 0.9);
    };
    img.src = page.url;
  }

  function movePage(index, direction) {
    const target = index + direction;
    if (target < 0 || target >= state.pages.length) return;
    const temp = state.pages[index];
    state.pages[index] = state.pages[target];
    state.pages[target] = temp;
    renderPageStrip();
  }

  function removePage(index) {
    URL.revokeObjectURL(state.pages[index].url);
    state.pages.splice(index, 1);
    renderPageStrip();
  }

  /* ---------------- Create / edit form ---------------- */
  function resetFormState() {
    state.source = "upload";
    state.selectedFile = null;
    state.pages.forEach((p) => URL.revokeObjectURL(p.url));
    state.pages = [];
    stopCamera();

    document.getElementById("agreementForm").reset();
    document.getElementById("agreementId").value = "";
    document.getElementById("fileInput").value = "";
    document.getElementById("fileChip").hidden = true;
    document.getElementById("dropZone").hidden = false;
    renderPageStrip();

    const tabs = document.getElementById("agreementSourceTabs");
    tabs.querySelectorAll(".tab").forEach((t, i) => t.classList.toggle("active", i === 0));
    document.getElementById("uploadPanel").hidden = false;
    document.getElementById("cameraPanel").hidden = true;

    document.getElementById("agreementProgressField").hidden = true;
    document.getElementById("agreementProgressBar").style.width = "0%";
    document.getElementById("cameraHint").textContent =
      "Works on both mobile and desktop browsers with camera access.";
  }

  function openForm(id) {
    resetFormState();
    const isEdit = !!id;

    document.getElementById("agreementModalTitle").textContent = isEdit
      ? "Edit agreement"
      : "New agreement";
    document.getElementById("agreementSourceField").hidden = isEdit;
    document.getElementById("uploadPanel").hidden = isEdit;
    document.getElementById("cameraPanel").hidden = true;

    if (isEdit) {
      const a = state.items.find((row) => row.id === id);
      if (!a) return UI.toast("Agreement not found. Refresh the page.", "error");
      document.getElementById("agreementId").value = a.id;
      document.getElementById("agreementProperty").value = a.property_id || "";
      document.getElementById("agreementTenant").value = a.tenant_id || "";
      document.getElementById("agreementStart").value = a.agreement_start || "";
      document.getElementById("agreementEnd").value = a.agreement_end || "";
      document.getElementById("agreementNotes").value = a.notes || "";
    }

    UI.openModal("agreementModal");
  }

  function uploadWithProgress(url, method, formData, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open(method, url, true);
      xhr.withCredentials = true;

      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable && onProgress) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      });

      xhr.onload = () => {
        let payload = null;
        try {
          payload = JSON.parse(xhr.responseText);
        } catch (e) {
          /* non-JSON response */
        }

        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(payload);
        } else {
          const detail =
            payload && payload.detail
              ? payload.detail
              : "Request failed (" + xhr.status + ").";
          reject(new Error(typeof detail === "string" ? detail : JSON.stringify(detail)));
        }
      };

      xhr.onerror = () =>
        reject(new Error("Cannot reach the server. Is the Python app still running?"));

      xhr.send(formData);
    });
  }

  async function save(event) {
    event.preventDefault();
    const button = document.getElementById("agreementSubmit");
    const id = document.getElementById("agreementId").value;

    const start = document.getElementById("agreementStart").value;
    const end = document.getElementById("agreementEnd").value;

    if (start && end && end < start) {
      return UI.toast("Agreement end date must be after the start date.", "error");
    }

    const formData = new FormData();
    formData.append("property_id", document.getElementById("agreementProperty").value || "");
    formData.append("tenant_id", document.getElementById("agreementTenant").value || "");
    formData.append("agreement_start", start || "");
    formData.append("agreement_end", end || "");
    formData.append("notes", document.getElementById("agreementNotes").value.trim() || "");

    let url = "/api/agreements";
    let method = "POST";

    if (id) {
      url = "/api/agreements/" + id;
      method = "PUT";
    } else {
      if (state.source === "upload") {
        if (!state.selectedFile) return UI.toast("Please choose a file to upload.", "error");
        formData.append("file", state.selectedFile);
      } else {
        if (!state.pages.length) return UI.toast("Please capture at least one page.", "error");
        state.pages.forEach((page, i) => {
          formData.append("pages", page.blob, "page-" + (i + 1) + ".jpg");
        });
      }
    }

    UI.setButtonLoading(button, true);
    const progressField = document.getElementById("agreementProgressField");
    const progressBar = document.getElementById("agreementProgressBar");

    if (!id) {
      progressField.hidden = false;
      progressBar.style.width = "0%";
    }

    try {
      await uploadWithProgress(url, method, formData, (pct) => {
        progressBar.style.width = pct + "%";
      });
      UI.toast(id ? "Agreement updated." : "Agreement saved.", "success");
      UI.closeModal("agreementModal");
      stopCamera();
      load();
    } catch (error) {
      UI.toast(error.message, "error");
    } finally {
      UI.setButtonLoading(button, false);
      progressField.hidden = true;
    }
  }

  /* ---------------- Replace file ---------------- */
  let replaceFile = null;

  function bindReplacePanel() {
    const zone = document.getElementById("replaceDropZone");
    const input = document.getElementById("replaceFileInput");

    document.getElementById("replaceBrowseBtn").addEventListener("click", () => input.click());
    input.addEventListener("change", () => {
      if (input.files[0]) setReplaceFile(input.files[0]);
    });

    ["dragenter", "dragover"].forEach((evt) =>
      zone.addEventListener(evt, (e) => {
        e.preventDefault();
        zone.classList.add("dropzone-active");
      })
    );

    ["dragleave", "drop"].forEach((evt) =>
      zone.addEventListener(evt, (e) => {
        e.preventDefault();
        zone.classList.remove("dropzone-active");
      })
    );

    zone.addEventListener("drop", (e) => {
      const file = e.dataTransfer.files && e.dataTransfer.files[0];
      if (file) setReplaceFile(file);
    });

    document.getElementById("replaceFileChipRemove").addEventListener("click", () => {
      replaceFile = null;
      input.value = "";
      document.getElementById("replaceFileChip").hidden = true;
      document.getElementById("replaceDropZone").hidden = false;
    });
  }

  function setReplaceFile(file) {
    const error = validateClientFile(file);
    if (error) return UI.toast(error, "error");
    replaceFile = file;
    document.getElementById("replaceFileChipName").textContent = file.name;
    document.getElementById("replaceFileChipMeta").textContent = formatSize(file.size);
    document.getElementById("replaceFileChip").hidden = false;
    document.getElementById("replaceDropZone").hidden = true;
  }

  function openReplace(id) {
    replaceFile = null;
    document.getElementById("replaceAgreementId").value = id;
    document.getElementById("replaceFileInput").value = "";
    document.getElementById("replaceFileChip").hidden = true;
    document.getElementById("replaceDropZone").hidden = false;
    document.getElementById("replaceProgressField").hidden = true;
    document.getElementById("replaceProgressBar").style.width = "0%";
    UI.openModal("replaceModal");
  }

  async function saveReplace(event) {
    event.preventDefault();
    if (!replaceFile) return UI.toast("Please choose a file first.", "error");

    const id = document.getElementById("replaceAgreementId").value;
    const button = document.getElementById("replaceSubmit");
    const formData = new FormData();
    formData.append("file", replaceFile);

    const progressField = document.getElementById("replaceProgressField");
    const progressBar = document.getElementById("replaceProgressBar");
    progressField.hidden = false;

    UI.setButtonLoading(button, true);
    try {
      await uploadWithProgress("/api/agreements/" + id + "/file", "PUT", formData, (pct) => {
        progressBar.style.width = pct + "%";
      });
      UI.toast("Document replaced.", "success");
      UI.closeModal("replaceModal");
      load();
    } catch (error) {
      UI.toast(error.message, "error");
    } finally {
      UI.setButtonLoading(button, false);
      progressField.hidden = true;
    }
  }
})();
