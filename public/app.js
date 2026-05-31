const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const uploadSection = document.getElementById("upload-section");
const loadingSection = document.getElementById("loading-section");
const resultSection = document.getElementById("result-section");
const loadingFilename = document.getElementById("loading-filename");
const markdownOutput = document.getElementById("markdown-output");
const resultMeta = document.getElementById("result-meta");
const copyBtn = document.getElementById("copy-btn");
const downloadBtn = document.getElementById("download-btn");
const newBtn = document.getElementById("new-btn");
const toast = document.getElementById("toast");
const formatsToggle = document.getElementById("formats-toggle");
const formatsList = document.getElementById("formats-list");
const sizeLimit = document.getElementById("size-limit");

let currentMarkdown = "";
let currentFilename = "output.md";
let blobUploadEnabled = false;
let maxSizeMb = 25;

function showToast(message, isError = false) {
  toast.textContent = message;
  toast.className = "toast show" + (isError ? " error" : "");
  setTimeout(() => toast.classList.remove("show"), 3000);
}

function showSection(section) {
  uploadSection.hidden = section !== "upload";
  loadingSection.hidden = section !== "loading";
  resultSection.hidden = section !== "result";
}

function parseError(data, fallback) {
  if (Array.isArray(data.detail)) {
    return data.detail.map((d) => d.msg || d).join(", ");
  }
  return data.detail || fallback;
}

async function loadFormats() {
  try {
    const res = await fetch("/api/formats");
    const data = await res.json();
    maxSizeMb = data.max_size_mb;
    blobUploadEnabled = Boolean(data.blob_upload);
    sizeLimit.textContent = `${maxSizeMb} MB max`;
    formatsList.innerHTML = data.extensions
      .map((ext) => `<span class="format-tag">${ext}</span>`)
      .join("");
  } catch {
    /* non-critical */
  }
}

formatsToggle.addEventListener("click", () => {
  const expanded = formatsToggle.getAttribute("aria-expanded") === "true";
  formatsToggle.setAttribute("aria-expanded", String(!expanded));
  formatsList.hidden = expanded;
});

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    fileInput.click();
  }
});

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("drag-over");
});

dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag-over"));

dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file) convertFile(file);
});

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (file) convertFile(file);
  fileInput.value = "";
});

async function convertViaBlob(file) {
  const urlRes = await fetch(
    `/api/upload-url?filename=${encodeURIComponent(file.name)}&size=${file.size}`
  );
  const urlData = await urlRes.json();
  if (!urlRes.ok) {
    throw new Error(parseError(urlData, "Could not start upload"));
  }

  const uploadRes = await fetch(urlData.upload_url, {
    method: "PUT",
    headers: {
      "x-ms-blob-type": "BlockBlob",
      "Content-Type": file.type || "application/octet-stream",
    },
    body: file,
  });
  if (!uploadRes.ok) {
    throw new Error("Upload to storage failed");
  }

  const convertRes = await fetch("/api/convert-blob", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      blob_name: urlData.blob_name,
      filename: file.name,
      size: file.size,
    }),
  });
  const convertData = await convertRes.json();
  if (!convertRes.ok) {
    throw new Error(parseError(convertData, "Conversion failed"));
  }
  return convertData;
}

async function convertViaDirect(file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch("/api/convert", { method: "POST", body: formData });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(parseError(data, "Conversion failed"));
  }
  return data;
}

async function convertFile(file) {
  if (file.size > maxSizeMb * 1024 * 1024) {
    showToast(`File too large. Max ${maxSizeMb} MB.`, true);
    return;
  }

  loadingFilename.textContent = file.name;
  showSection("loading");

  try {
    const data = blobUploadEnabled
      ? await convertViaBlob(file)
      : await convertViaDirect(file);

    currentMarkdown = data.markdown;
    currentFilename = data.filename;
    markdownOutput.textContent = currentMarkdown;
    resultMeta.textContent = `${data.filename} · ${currentMarkdown.length.toLocaleString()} chars`;
    showSection("result");
  } catch (err) {
    showSection("upload");
    showToast(err.message, true);
  }
}

copyBtn.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(currentMarkdown);
    const label = copyBtn.textContent;
    copyBtn.textContent = "Copied";
    copyBtn.classList.add("copied");
    setTimeout(() => {
      copyBtn.textContent = label;
      copyBtn.classList.remove("copied");
    }, 1500);
  } catch {
    showToast("Could not copy", true);
  }
});

downloadBtn.addEventListener("click", () => {
  const blob = new Blob([currentMarkdown], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = currentFilename;
  a.click();
  URL.revokeObjectURL(url);
  showToast("Downloaded");
});

newBtn.addEventListener("click", () => {
  currentMarkdown = "";
  showSection("upload");
});

loadFormats();
