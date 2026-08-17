const usefulAttributes = [
  'text', 'content-desc', 'resource-id', 'class', 'name', 'label', 'value', 'type', 'role',
  'enabled', 'clickable', 'checked', 'selected', 'focused', 'visible', 'displayed',
  'bounds', 'x', 'y', 'width', 'height',
];

function isXml(content: string) {
  return content.trimStart().startsWith('<');
}

function embeddedXml(content: string) {
  try {
    const value = JSON.parse(content) as unknown;
    return value && typeof value === 'object' && !Array.isArray(value) && typeof (value as { xml?: unknown }).xml === 'string'
      ? (value as { xml: string }).xml
      : null;
  } catch {
    return null;
  }
}

function parseXml(content: string): Document | null {
  const xml = isXml(content) ? content : embeddedXml(content);
  if (!xml || typeof DOMParser === 'undefined') return null;
  const document = new DOMParser().parseFromString(xml, 'application/xml');
  return document.querySelector('parsererror') ? null : document;
}

function compactAttributes(element: Element) {
  const seen = new Set<string>();
  const pairs: string[] = [];
  const push = (name: string, value: string | null) => {
    if (!value || seen.has(name)) return;
    seen.add(name);
    pairs.push(`${name}=${JSON.stringify(value)}`);
  };
  for (const name of usefulAttributes) push(name, element.getAttribute(name));
  for (const attribute of Array.from(element.attributes)) push(attribute.name, attribute.value);
  return pairs.length ? ` ${pairs.join(' ')}` : '';
}

function elementLabel(element: Element) {
  return `${element.tagName}${compactAttributes(element)}`;
}

function walk(element: Element, depth: number, lines: string[]) {
  lines.push(`${'  '.repeat(depth)}${elementLabel(element)}`);
  for (const child of Array.from(element.children)) walk(child, depth + 1, lines);
}

export function xmlToReadableTree(content: string): string | null {
  const document = parseXml(content);
  const root = document?.documentElement;
  if (!root) return null;
  const lines: string[] = [];
  walk(root, 0, lines);
  return lines.join('\n');
}

export function formatUiTreeContent(content: string) {
  return xmlToReadableTree(content) ?? content;
}

export function isStructuredXmlTree(content: string) {
  return xmlToReadableTree(content) !== null;
}