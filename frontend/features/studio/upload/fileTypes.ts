/** Browsers often report Python source as plain text or omit its media type. */
export function mimeForFile(mime: string, filename: string): string {
  const base = mime.split(";")[0].trim().toLowerCase();
  if (/\.py$/i.test(filename) && ["", "text/plain", "application/octet-stream", "application/x-python", "text/x-python-script"].includes(base)) {
    return "text/x-python";
  }
  return base;
}
