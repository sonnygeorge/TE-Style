const CSV_PATH = "te-style_labels.csv";

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

    renderRows(rows);
    setStatus(`Loaded ${rows.length} label row(s).`);
  } catch (error) {
    setStatus(error instanceof Error ? error.message : "Failed to load labels.", true);
  }
}

init();
