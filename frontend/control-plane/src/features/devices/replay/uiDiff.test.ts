import { diffLines } from './uiDiff';

it('aligns inserted and deleted lines without shifting later context', () => {
  const inserted = diffLines('a\nb\nc', 'a\nnew\nb\nc');
  expect(inserted.map((row) => [row.kind, row.before, row.after])).toEqual([
    ['context', 'a', 'a'],
    ['added', '', 'new'],
    ['context', 'b', 'b'],
    ['context', 'c', 'c'],
  ]);
  const removed = diffLines('a\nold\nb', 'a\nb');
  expect(removed.map((row) => row.kind)).toEqual(['context', 'removed', 'context']);
});

it('handles line-heavy snapshots with bounded-memory alignment', () => {
  const before = Array.from({ length: 20_000 }, (_, index) => `unique-${index}`).join('\n');
  const after = `${before}\nlast`;
  const rows = diffLines(before, after);
  expect(rows).toHaveLength(20_001);
  expect(rows.at(-1)).toMatchObject({ kind: 'added', after: 'last' });
});

it('preserves repeated-line context around an insertion', () => {
  expect(diffLines('x\nx', 'new\nx\nx').map((row) => [row.kind, row.before, row.after])).toEqual([
    ['added', '', 'new'],
    ['context', 'x', 'x'],
    ['context', 'x', 'x'],
  ]);
});