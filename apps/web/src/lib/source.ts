export function sourceSegments(
  text: string,
  highlight?: { char_start: number; char_end: number } | null,
) {
  // API offsets are Python Unicode code-point indices, not JavaScript UTF-16 offsets.
  const chars = Array.from(text);
  if (
    !highlight ||
    highlight.char_start < 0 ||
    highlight.char_end <= highlight.char_start ||
    highlight.char_end > chars.length
  )
    return { before: text, marked: "", after: "" };
  return {
    before: chars.slice(0, highlight.char_start).join(""),
    marked: chars.slice(highlight.char_start, highlight.char_end).join(""),
    after: chars.slice(highlight.char_end).join(""),
  };
}
