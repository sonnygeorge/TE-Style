const CSV_PATH = "te-style_labels.csv";
const VIDEOS_PREFIX = "videos/";

const appState = {
  allRows: [],
  selectedDirectory: "",
};

function parseCsvLine(line) {
  const cells = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    const nextChar = i + 1 < line.length ? line[i + 1] : "";

    if (char === '"' && inQuotes && nextChar === '"') {
      current += '"';
      i += 1;
      continue;
    }

    if (char === '"') {
      inQuotes = !inQuotes;
      continue;
    }

    if (char === "," && !inQuotes) {
      cells.push(current);
      current = "";
      continue;
    }

    current += char;
  }

  cells.push(current);
  return cells;
}

function parseCsv(text) {
  const rawLines = text.replace(/\r\n/g, "\n").split("\n");
  const lines = rawLines.filter((line) => line.trim().length > 0);
  if (lines.length === 0) return { headers: [], rows: [] };

  const headers = parseCsvLine(lines[0]).map((header) => header.trim());
  const rows = lines.slice(1).map((line) => {
    const values = parseCsvLine(line);
    const row = {};
    headers.forEach((header, idx) => {
      row[header] = (values[idx] ?? "").trim();
    });
    return row;
  });

  return { headers, rows };
}

function setStatus(message, isError = false) {
  const status = document.getElementById("status");
  status.textContent = message;
  status.style.color = isError ? "#b91c1c" : "#1f2937";
}

function buildVideoCell(videoPath) {
  const cell = document.createElement("td");
  cell.className = "video-cell";

  if (!videoPath) {
    cell.textContent = "No video path";
    return cell;
  }

  const video = document.createElement("video");
  video.controls = true;
  video.preload = "metadata";
  video.src = encodeURI(videoPath);
  video.title = videoPath;

  cell.appendChild(video);
  return cell;
}

function renderRows(rows) {
  const table = document.getElementById("labels-table");
  const tbody = document.getElementById("labels-table-body");
  tbody.innerHTML = "";

  rows.forEach((row) => {
    const tr = document.createElement("tr");

    ["actor_description", "task", "te_style_description"].forEach((key) => {
      const td = document.createElement("td");
      td.textContent = row[key] || "";
      tr.appendChild(td);
    });

    tr.appendChild(buildVideoCell(row.video || ""));
    tbody.appendChild(tr);
  });

  table.hidden = false;
}

function getRowDirectoryUnderVideos(videoPath) {
  const normalized = (videoPath || "").replace(/\\/g, "/").trim();
  if (!normalized.startsWith(VIDEOS_PREFIX)) {
    return null;
  }
  const relative = normalized.slice(VIDEOS_PREFIX.length);
  const slashIndex = relative.lastIndexOf("/");
  if (slashIndex < 0) {
    return "";
  }
  return relative.slice(0, slashIndex);
}

function listFilterDirectories(rows) {
  const directories = new Set();
  rows.forEach((row) => {
    const rowDir = getRowDirectoryUnderVideos(row.video || "");
    if (!rowDir) return;

    const parts = rowDir.split("/").filter(Boolean);
    let current = "";
    parts.forEach((part) => {
      current = current ? `${current}/${part}` : part;
      directories.add(current);
    });
  });
  return [...directories].sort((a, b) => a.localeCompare(b));
}

function populateDirectoryFilter(rows) {
  const select = document.getElementById("directory-filter");
  const directories = listFilterDirectories(rows);
  select.innerHTML = "";

  const allOption = document.createElement("option");
  allOption.value = "";
  allOption.textContent = "All videos/";
  select.appendChild(allOption);

  directories.forEach((dir) => {
    const option = document.createElement("option");
    option.value = dir;
    option.textContent = dir;
    select.appendChild(option);
  });
}

function rowMatchesDirectory(row, selectedDirectory) {
  if (!selectedDirectory) return true;
  const rowDir = getRowDirectoryUnderVideos(row.video || "");
  if (rowDir === null) return false;
  return rowDir === selectedDirectory || rowDir.startsWith(`${selectedDirectory}/`);
}

function renderFilteredRows() {
  const filteredRows = appState.allRows.filter((row) =>
    rowMatchesDirectory(row, appState.selectedDirectory)
  );
  renderRows(filteredRows);

  const total = appState.allRows.length;
  if (appState.selectedDirectory) {
    setStatus(
      `Showing ${filteredRows.length} of ${total} row(s) for videos/${appState.selectedDirectory}`
    );
  } else {
    setStatus(`Loaded ${total} label row(s).`);
  }
}

function bindFilterEvents() {
  const select = document.getElementById("directory-filter");
  const clearButton = document.getElementById("clear-filter");

  select.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLSelectElement)) return;
    appState.selectedDirectory = target.value;
    renderFilteredRows();
  });

  clearButton.addEventListener("click", () => {
    appState.selectedDirectory = "";
    select.value = "";
    renderFilteredRows();
  });
}

async function init() {
  try {
    const response = await fetch(CSV_PATH, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Could not load ${CSV_PATH} (${response.status})`);
    }

    const csvText = await response.text();
    const { rows } = parseCsv(csvText);

    if (!rows.length) {
      setStatus("No labels found in CSV.");
      return;
    }

    appState.allRows = rows;
    populateDirectoryFilter(rows);
    bindFilterEvents();
    renderFilteredRows();
  } catch (error) {
    setStatus(error instanceof Error ? error.message : "Failed to load labels.", true);
  }
}

init();
