import { downloadBlob } from "./utils";
import type { OverlayCollection, SceneSlot } from "./types";

export function downloadSceneRasters(slots: SceneSlot[]): boolean {
  const rasters = slots.filter((s) => s.file);
  if (!rasters.length) return false;
  for (const slot of rasters) {
    if (slot.file) downloadBlob(slot.filename, slot.file);
  }
  return true;
}

function escapePdf(text: string) {
  return text.replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");
}

function wrap(text: string, width: number): string[] {
  const words = text.split(/\s+/);
  const lines: string[] = [];
  let cur = "";
  for (const word of words) {
    const next = cur ? `${cur} ${word}` : word;
    if (next.length > width) {
      if (cur) lines.push(cur);
      cur = word;
    } else {
      cur = next;
    }
  }
  if (cur) lines.push(cur);
  return lines;
}

export function downloadReportPdf(jobId: string, query: string, answer: string) {
  const lines = [
    "SatQuery report",
    "",
    `Job  ${jobId}`,
    "",
    "Query",
    ...wrap(query, 86),
    "",
    "Answer",
    ...wrap(answer, 86),
  ];
  const startY = 800;
  const commands = ["BT", "/F1 11 Tf", "1 0 0 1 48 " + startY + " Tm", "16 TL"];
  for (const line of lines) {
    commands.push(`(${escapePdf(line)}) Tj`, "T*");
  }
  commands.push("ET");
  const stream = commands.join("\n");
  const objects = [
    "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
    "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
    "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj",
    `4 0 obj << /Length ${stream.length} >> stream\n${stream}\nendstream endobj`,
    "5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
  ];
  let offset = 9;
  const xref = ["xref", "0 6", "0000000000 65535 f "];
  const body: string[] = ["%PDF-1.4"];
  for (const obj of objects) {
    xref.push(`${String(offset).padStart(10, "0")} 00000 n `);
    body.push(obj);
    offset += obj.length + 1;
  }
  const xrefStart = offset;
  body.push(xref.join("\n"), `trailer << /Size 6 /Root 1 0 R >>`, `startxref`, String(xrefStart), "%%EOF");
  downloadBlob(`report-${jobId.slice(0, 8)}.pdf`, new Blob([body.join("\n")], { type: "application/pdf" }));
}

export function downloadGeoJSON(jobId: string, overlays: OverlayCollection) {
  downloadBlob(
    `export-${jobId.slice(0, 8)}.geojson`,
    new Blob([JSON.stringify(overlays, null, 2)], { type: "application/geo+json" }),
  );
}

export function downloadKml(jobId: string, overlays: OverlayCollection) {
  const placemarks = overlays.features
    .map((f) => {
      const coords = f.geometry.coordinates[0].map(([lng, lat]) => `${lng},${lat},0`).join(" ");
      return `<Placemark><name>${f.properties.kind}</name><Polygon><outerBoundaryIs><LinearRing><coordinates>${coords}</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>`;
    })
    .join("");
  const kml = `<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>${placemarks}</Document></kml>`;
  downloadBlob(`export-${jobId.slice(0, 8)}.kml`, new Blob([kml], { type: "application/vnd.google-earth.kml+xml" }));
}
