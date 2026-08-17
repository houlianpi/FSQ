declare module 'ts-ebml/dist/EBML.js' {
  const EBML: {
    Decoder: new () => { decode(buffer: ArrayBuffer): unknown[] };
    Reader: new () => {
      logging: boolean;
      drop_default_duration: boolean;
      duration: number;
      cues: unknown[];
      trackInfo?: { trackNumber?: number };
      metadatas: unknown[];
      metadataSize: number;
      read(element: unknown): void;
      stop(): void;
    };
    tools: { makeMetadataSeekable(metadata: unknown[], duration: number, cues: unknown[]): Uint8Array };
  };
  export default EBML;
}
