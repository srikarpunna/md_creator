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

async function loadFormats() {
  try {
    const res = await fetch("/api/formats");
    const data = await res.json();
    sizeLimit.textContent = `${data.max_size_mb} MB max`;
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

async function convertFile(file) {
  loadingFilename.textContent = file.name;
  showSection("loading");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/convert", { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok) {
      const detail = Array.isArray(data.detail)
        ? data.detail.map((d) => d.msg || d).join(", ")
        : data.detail;
      throw new Error(detail || "Conversion failed");
    }

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
