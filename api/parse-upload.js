const zlib = require("node:zlib");

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ ok: false, error: "Method not allowed" });
    return;
  }

  try {
    const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : req.body || {};
    const name = String(body.name || "upload.xlsx");
    const dataUrl = String(body.dataUrl || "");
    if (!dataUrl.startsWith("data:")) {
      res.status(400).json({ ok: false, error: "dataUrl is required" });
      return;
    }

    const base64 = dataUrl.split(",")[1] || "";
    const buffer = Buffer.from(base64, "base64");
    const text = parseXlsxText(buffer).slice(0, 900000);
    res.status(200).json({
      ok: true,
      name,
      text,
      rows: text ? text.split("\n").length : 0,
    });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message || "xlsx parse failed" });
  }
};

function parseXlsxText(buffer) {
  const entries = unzipEntries(buffer);
  const shared = parseSharedStrings(entries.get("xl/sharedStrings.xml") || "");
  const workbook = entries.get("xl/workbook.xml") || "";
  const rels = entries.get("xl/_rels/workbook.xml.rels") || "";
  const sheetNames = parseSheetNames(workbook, rels);
  const lines = [];

  for (const [path, xml] of entries.entries()) {
    if (!/^xl\/worksheets\/sheet\d+\.xml$/.test(path)) continue;
    const sheetFile = path.split("/").pop();
    const sheetName = sheetNames.get(sheetFile) || sheetFile.replace(".xml", "");
    lines.push(`## Sheet: ${sheetName}`);
    lines.push(...parseSheetRows(xml, shared));
  }
  return lines.join("\n");
}

function unzipEntries(buffer) {
  const eocdOffset = findSignature(buffer, 0x06054b50, Math.max(0, buffer.length - 70000));
  if (eocdOffset < 0) throw new Error("Invalid xlsx zip: EOCD not found");
  const totalEntries = buffer.readUInt16LE(eocdOffset + 10);
  const centralOffset = buffer.readUInt32LE(eocdOffset + 16);
  const entries = new Map();
  let offset = centralOffset;

  for (let index = 0; index < totalEntries; index += 1) {
    if (buffer.readUInt32LE(offset) !== 0x02014b50) break;
    const method = buffer.readUInt16LE(offset + 10);
    const compressedSize = buffer.readUInt32LE(offset + 20);
    const filenameLength = buffer.readUInt16LE(offset + 28);
    const extraLength = buffer.readUInt16LE(offset + 30);
    const commentLength = buffer.readUInt16LE(offset + 32);
    const localOffset = buffer.readUInt32LE(offset + 42);
    const filename = buffer.slice(offset + 46, offset + 46 + filenameLength).toString("utf8");

    if (buffer.readUInt32LE(localOffset) === 0x04034b50) {
      const localNameLength = buffer.readUInt16LE(localOffset + 26);
      const localExtraLength = buffer.readUInt16LE(localOffset + 28);
      const dataStart = localOffset + 30 + localNameLength + localExtraLength;
      const compressed = buffer.slice(dataStart, dataStart + compressedSize);
      let data;
      if (method === 0) data = compressed;
      else if (method === 8) data = zlib.inflateRawSync(compressed);
      else data = null;
      if (data && /\.(xml|rels)$/.test(filename)) entries.set(filename, data.toString("utf8"));
    }

    offset += 46 + filenameLength + extraLength + commentLength;
  }
  return entries;
}

function findSignature(buffer, signature, start) {
  for (let offset = buffer.length - 4; offset >= start; offset -= 1) {
    if (buffer.readUInt32LE(offset) === signature) return offset;
  }
  return -1;
}

function parseSharedStrings(xml) {
  const strings = [];
  const siBlocks = xml.match(/<si[\s\S]*?<\/si>/g) || [];
  for (const block of siBlocks) strings.push(cleanXml(block));
  return strings;
}

function parseSheetNames(workbookXml, relsXml) {
  const relTargets = new Map();
  const relBlocks = relsXml.match(/<Relationship\b[^>]*>/g) || [];
  for (const block of relBlocks) {
    const id = getAttr(block, "Id");
    const target = getAttr(block, "Target");
    if (id && target) relTargets.set(id, target.split("/").pop());
  }

  const names = new Map();
  const sheetBlocks = workbookXml.match(/<sheet\b[^>]*>/g) || [];
  for (const block of sheetBlocks) {
    const name = getAttr(block, "name");
    const relId = getAttr(block, "r:id");
    const file = relTargets.get(relId);
    if (name && file) names.set(file, name);
  }
  return names;
}

function parseSheetRows(xml, shared) {
  const rows = [];
  const rowBlocks = xml.match(/<row\b[\s\S]*?<\/row>/g) || [];
  for (const rowBlock of rowBlocks) {
    const cells = [];
    const cellBlocks = rowBlock.match(/<c\b[\s\S]*?<\/c>/g) || [];
    for (const cell of cellBlocks) {
      const type = getAttr(cell, "t");
      let value = "";
      if (type === "s") {
        const index = Number((cell.match(/<v[^>]*>([\s\S]*?)<\/v>/) || [])[1]);
        value = shared[index] || "";
      } else if (type === "inlineStr") {
        value = cleanXml(cell);
      } else {
        value = decodeXml((cell.match(/<v[^>]*>([\s\S]*?)<\/v>/) || [])[1] || "");
      }
      cells.push(value);
    }
    const line = cells.join("\t").replace(/\s+\t/g, "\t").replace(/\t\s+/g, "\t").trim();
    if (line) rows.push(line);
  }
  return rows;
}

function getAttr(tag, name) {
  const pattern = new RegExp(`${name.replace(":", "\\:")}=["']([^"']+)["']`);
  return (tag.match(pattern) || [])[1] || "";
}

function cleanXml(xml) {
  return decodeXml(String(xml || "").replace(/<[^>]+>/g, " ")).replace(/\s+/g, " ").trim();
}

function decodeXml(value) {
  return String(value || "")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&#(\d+);/g, (_, code) => String.fromCharCode(Number(code)));
}
