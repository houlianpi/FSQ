import { useEffect, useId, useRef, type ReactNode } from 'react';

interface DialogFrameProps {
  title: string;
  children: ReactNode;
  onClose: () => void;
}

export function DialogFrame({ title, children, onClose }: DialogFrameProps) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    returnFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const dialog = dialogRef.current;
    const focusable = () => dialog?.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])');
    (dialog?.querySelector<HTMLElement>('[data-dialog-initial]') ?? focusable()?.[0] ?? dialog)?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      const controls = focusable();
      if (event.key !== 'Tab' || !controls?.length) return;
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      window.setTimeout(() => returnFocusRef.current?.focus(), 0);
    };
  }, []);

  return <div className="config-dialog-backdrop">
    <div ref={dialogRef} className="config-dialog" role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}>
      <h2 id={titleId}>{title}</h2>
      {children}
    </div>
  </div>;
}