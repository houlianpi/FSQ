import { formatUiTreeContent, isStructuredXmlTree, xmlToReadableTree } from './uiTreeFormat';

it('formats XML UI snapshots into a readable attribute tree', () => {
  const xml = '<hierarchy><node text="Sign in" class="Button" bounds="[0,0][100,40]" enabled="true"><node content-desc="Email" resource-id="email" /></node></hierarchy>';

  expect(isStructuredXmlTree(xml)).toBe(true);
  expect(xmlToReadableTree(xml)).toBe([
    'hierarchy',
    '  node text="Sign in" class="Button" enabled="true" bounds="[0,0][100,40]"',
    '    node content-desc="Email" resource-id="email"',
  ].join('\n'));
});

it('formats Android JSON-wrapped XML UI snapshots', () => {
  const payload = JSON.stringify({ xml: '<hierarchy><node text="Continue" bounds="[1,2][3,4]" /></hierarchy>' });

  expect(isStructuredXmlTree(payload)).toBe(true);
  expect(formatUiTreeContent(payload)).toBe([
    'hierarchy',
    '  node text="Continue" bounds="[1,2][3,4]"',
  ].join('\n'));
});

it('leaves non-XML or invalid XML unchanged', () => {
  expect(formatUiTreeContent('{"value":true}')).toBe('{"value":true}');
  expect(formatUiTreeContent('<hierarchy><node></hierarchy>')).toBe('<hierarchy><node></hierarchy>');
});
