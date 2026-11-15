/** Browsers often report Python source as plain text or omit its media type. */
export function mimeForFile(mime: string, filename: string): string {
  const base = mime.split(";")[0].trim().toLowerCase();
  const generic = ["", "application/octet-stream", "text/plain", "application/x-download"];
  if (/\.csv$/i.test(filename) && [...generic, "application/vnd.ms-excel"].includes(base)) return "text/csv";
  if (/\.json$/i.test(filename) && [...generic, "text/json"].includes(base)) return "application/json";
  if (/\.txt$/i.test(filename) && generic.includes(base)) return "text/plain";
  if (/\.tsv$/i.test(filename) && [...generic, "text/tab-separated-values"].includes(base)) return "text/plain";
  if (/\.py$/i.test(filename) && ["", "text/plain", "application/octet-stream", "application/x-python", "text/x-python-script"].includes(base)) {
    return "text/x-python";
  }
  if (/\.js$/i.test(filename) && ["", "text/plain", "application/octet-stream", "application/x-download", "application/x-javascript"].includes(base)) {
    return "text/javascript";
  }
  if (/\.sh$/i.test(filename) && [...generic, "application/x-sh", "text/x-sh"].includes(base)) return "text/x-shellscript";
  // Linux/Windows browsers often leave phone video (.MOV in particular) untyped.
  const binaryGeneric = ["", "application/octet-stream", "application/x-download"];
  if (/\.mov$/i.test(filename) && binaryGeneric.includes(base)) return "video/quicktime";
  if (/\.mp4$/i.test(filename) && binaryGeneric.includes(base)) return "video/mp4";
  if (/\.webm$/i.test(filename) && binaryGeneric.includes(base)) return "video/webm";
  return base;
}
