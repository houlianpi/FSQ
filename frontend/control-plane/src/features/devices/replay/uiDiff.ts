export interface DiffRow {
  beforeNumber: number | null;
  afterNumber: number | null;
  before: string;
  after: string;
  kind: 'context' | 'changed' | 'removed' | 'added';
}

export function diffLines(before: string, after: string): DiffRow[] {
  const left = before.split('\n');
  const right = after.split('\n');
  const rows: DiffRow[] = [];
  alignRange(rows, left, right, 0, left.length, 0, right.length);
  return rows;
}

function alignRange(rows: DiffRow[], left: string[], right: string[], initialLeftStart: number, initialLeftEnd: number, initialRightStart: number, initialRightEnd: number) {
  let leftStart = initialLeftStart;
  let rightStart = initialRightStart;
  const suffix: DiffRow[] = [];
  let leftEnd = initialLeftEnd;
  let rightEnd = initialRightEnd;
  while (leftStart < leftEnd && rightStart < rightEnd && left[leftStart] === right[rightStart]) {
    rows.push(contextRow(left, right, leftStart, rightStart)); leftStart += 1; rightStart += 1;
  }
  while (leftStart < leftEnd && rightStart < rightEnd && left[leftEnd - 1] === right[rightEnd - 1]) {
    leftEnd -= 1; rightEnd -= 1; suffix.unshift(contextRow(left, right, leftEnd, rightEnd));
  }
  if (leftStart === leftEnd || rightStart === rightEnd) {
    appendGap(rows, left, right, leftStart, leftEnd, rightStart, rightEnd);
    rows.push(...suffix);
    return;
  }
  const anchors = patienceAnchors(left, right, leftStart, leftEnd, rightStart, rightEnd);
  if (!anchors.length) {
    appendGap(rows, left, right, leftStart, leftEnd, rightStart, rightEnd);
    rows.push(...suffix);
    return;
  }
  let previousLeft = leftStart;
  let previousRight = rightStart;
  for (const [leftIndex, rightIndex] of anchors) {
    alignRange(rows, left, right, previousLeft, leftIndex, previousRight, rightIndex);
    rows.push(contextRow(left, right, leftIndex, rightIndex));
    previousLeft = leftIndex + 1; previousRight = rightIndex + 1;
  }
  alignRange(rows, left, right, previousLeft, leftEnd, previousRight, rightEnd);
  rows.push(...suffix);
}

function contextRow(left: string[], right: string[], leftIndex: number, rightIndex: number): DiffRow {
  return { beforeNumber: leftIndex + 1, afterNumber: rightIndex + 1, before: left[leftIndex], after: right[rightIndex], kind: 'context' };
}

function appendGap(rows: DiffRow[], left: string[], right: string[], leftStart: number, leftEnd: number, rightStart: number, rightEnd: number) {
  const leftCount = leftEnd - leftStart;
  const rightCount = rightEnd - rightStart;
  const paired = Math.min(leftCount, rightCount);
  for (let index = 0; index < paired; index += 1) {
    rows.push({ beforeNumber: leftStart + index + 1, afterNumber: rightStart + index + 1, before: left[leftStart + index], after: right[rightStart + index], kind: 'changed' });
  }
  for (let index = paired; index < leftCount; index += 1) rows.push({ beforeNumber: leftStart + index + 1, afterNumber: null, before: left[leftStart + index], after: '', kind: 'removed' });
  for (let index = paired; index < rightCount; index += 1) rows.push({ beforeNumber: null, afterNumber: rightStart + index + 1, before: '', after: right[rightStart + index], kind: 'added' });
}

function patienceAnchors(left: string[], right: string[], leftStart: number, leftEnd: number, rightStart: number, rightEnd: number): Array<readonly [number, number]> {
  const leftUnique = uniqueIndexes(left, leftStart, leftEnd);
  const rightUnique = uniqueIndexes(right, rightStart, rightEnd);
  const candidates = [...leftUnique].flatMap(([line, leftIndex]) => rightUnique.has(line) ? [[leftIndex, rightUnique.get(line)!] as const] : []);
  const tails: number[] = [];
  const previous = Array<number>(candidates.length).fill(-1);
  for (let index = 0; index < candidates.length; index += 1) {
    const rightIndex = candidates[index][1];
    let low = 0; let high = tails.length;
    while (low < high) { const middle = (low + high) >> 1; if (candidates[tails[middle]][1] < rightIndex) low = middle + 1; else high = middle; }
    if (low > 0) previous[index] = tails[low - 1];
    tails[low] = index;
  }
  const anchors: Array<readonly [number, number]> = [];
  let current = tails.at(-1) ?? -1;
  while (current >= 0) { anchors.push(candidates[current]); current = previous[current]; }
  return anchors.reverse();
}

function uniqueIndexes(lines: string[], start: number, end: number) {
  const counts = new Map<string, number>();
  for (let index = start; index < end; index += 1) counts.set(lines[index], (counts.get(lines[index]) ?? 0) + 1);
  const indexes = new Map<string, number>();
  for (let index = start; index < end; index += 1) { if (counts.get(lines[index]) === 1) indexes.set(lines[index], index); }
  return indexes;
}

export function changedSegments(before: string, after: string) {
  let prefix = 0;
  while (prefix < before.length && prefix < after.length && before[prefix] === after[prefix]) prefix += 1;
  let suffix = 0;
  while (suffix < before.length - prefix && suffix < after.length - prefix && before[before.length - suffix - 1] === after[after.length - suffix - 1]) suffix += 1;
  return {
    before: [before.slice(0, prefix), before.slice(prefix, before.length - suffix || undefined), suffix ? before.slice(-suffix) : ''],
    after: [after.slice(0, prefix), after.slice(prefix, after.length - suffix || undefined), suffix ? after.slice(-suffix) : ''],
  };
}
