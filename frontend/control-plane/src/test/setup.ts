import '@testing-library/jest-dom/vitest';

class MockEventSource {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  readonly CONNECTING = 0;
  readonly OPEN = 1;
  readonly CLOSED = 2;
  readonly url: string;
  readonly withCredentials = false;
  readyState = MockEventSource.OPEN;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onopen: ((event: Event) => void) | null = null;
  constructor(url: string | URL) { this.url = String(url); }
  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() { return true; }
  close() { this.readyState = MockEventSource.CLOSED; }
}

Object.defineProperty(window, 'EventSource', { configurable: true, writable: true, value: MockEventSource });
Object.defineProperty(globalThis, 'EventSource', { configurable: true, writable: true, value: MockEventSource });
Object.defineProperty(window, 'matchMedia', { configurable: true, writable: true, value: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }) });
if (!URL.createObjectURL) URL.createObjectURL = () => 'blob:test';
if (!URL.revokeObjectURL) URL.revokeObjectURL = () => undefined;
