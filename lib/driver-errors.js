/** Preserve structured refusals even when the CLI exits nonzero. */
export function driverFailure(stdout = '', stderr = '') {
  for (const text of [stdout, stderr]) {
    const start = text.indexOf('{'), end = text.lastIndexOf('}')
    if (start < 0 || end < start) continue
    try {
      const value = JSON.parse(text.slice(start, end + 1))
      if (value && typeof value === 'object' && !Array.isArray(value)) return value
    } catch { /* Ordinary diagnostic output remains an exception. */ }
  }
  return null
}
