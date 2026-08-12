import { useEffect, useRef, useState, type ReactNode } from 'react';
import { ControlPlaneSidebar } from './ControlPlaneSidebar';
import { CONTROL_PLANE_NAVIGATION, type ControlPlanePageId, type WorkspaceNavigationItem } from './navigation';
import './shell.css';

interface ControlPlaneShellProps {
  activePage: ControlPlanePageId;
  title: string;
  description: string;
  titleActions?: ReactNode;
  children: ReactNode;
  workspaces?: readonly WorkspaceNavigationItem[];
  onNavigate?: (page: ControlPlanePageId) => void;
}

export function ControlPlaneShell({ activePage, title, description, titleActions, children, workspaces, onNavigate }: ControlPlaneShellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [narrow, setNarrow] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const query = window.matchMedia('(max-width: 980px)');
    const update = () => setNarrow(query.matches);
    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);

  useEffect(() => {
    if (!drawerOpen) return;
    const drawer = drawerRef.current;
    const focusable = drawer?.querySelectorAll<HTMLElement>('button:not([disabled]), [tabindex]:not([tabindex="-1"])');
    focusable?.[0]?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setDrawerOpen(false);
        requestAnimationFrame(() => toggleRef.current?.focus());
        return;
      }
      if (event.key !== 'Tab' || !focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [drawerOpen]);

  const closeDrawer = () => {
    setDrawerOpen(false);
    requestAnimationFrame(() => toggleRef.current?.focus());
  };

  return (
    <div className="cp-shell">
      <button
        ref={toggleRef}
        className="cp-menu-button"
        type="button"
        aria-label="Open navigation"
        aria-expanded={drawerOpen}
        aria-controls="control-plane-sidebar"
        onClick={() => setDrawerOpen(true)}
      >☰</button>
      {drawerOpen && <button className="cp-drawer-scrim" type="button" aria-label="Dismiss navigation overlay" onClick={closeDrawer} />}
      <aside ref={drawerRef} id="control-plane-sidebar" className={`cp-sidebar${drawerOpen ? ' cp-sidebar--open' : ''}`} aria-label="Control Plane sidebar" aria-hidden={narrow && !drawerOpen ? true : undefined} inert={narrow && !drawerOpen ? true : undefined}>
        <button className="cp-drawer-close" type="button" aria-label="Close navigation" onClick={closeDrawer}>×</button>
        <ControlPlaneSidebar activePage={activePage} navigation={CONTROL_PLANE_NAVIGATION} workspaces={workspaces} onNavigate={(page) => { onNavigate?.(page); closeDrawer(); }} />
      </aside>
      <div className="cp-main-column">
        <header className="cp-titlebar">
          <div className="cp-title-context"><strong>{title}</strong><small>{description}</small></div>
          {titleActions && <div className="cp-title-actions">{titleActions}</div>}
        </header>
        <main className="cp-page-outlet" id="main-content">{children}</main>
      </div>
    </div>
  );
}
