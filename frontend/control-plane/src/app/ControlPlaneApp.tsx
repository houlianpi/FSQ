import { useState } from 'react';
import { ControlPlaneShell } from './shell/ControlPlaneShell';
import type { ControlPlanePageId } from './shell/navigation';
import { ConfigPage } from '../features/config/ConfigPage';
import { DevicesPage } from '../features/devices/DevicesPage';

export function ControlPlaneApp() {
  const [activePage, setActivePage] = useState<'devices' | 'config'>('devices');
  const [configDirty, setConfigDirty] = useState(false);
  const navigate = (page: ControlPlanePageId) => {
    if (page !== 'devices' && page !== 'config') return;
    if (activePage === 'config' && page === 'devices' && configDirty && !window.confirm('Discard unsaved Azure changes?')) return;
    setConfigDirty(false);
    setActivePage(page);
  };

  if (activePage === 'config') return <ControlPlaneShell
    activePage="config" title="Config" description="Manage the active model provider used by the next complete FSQ task."
    onNavigate={navigate}
  ><ConfigPage onDirtyChange={setConfigDirty} /></ControlPlaneShell>;

  return <DevicesPage renderShell={(toolbar, content) => <ControlPlaneShell
    activePage="devices" title="Device workspace"
    description="Select a target, choose how FSQ should test it, and follow real evidence while the run progresses."
    titleActions={toolbar} onNavigate={navigate}
  >{content}</ControlPlaneShell>} />;
}
