import { ControlPlaneShell } from './shell/ControlPlaneShell';
import { DevicesPage } from '../features/devices/DevicesPage';

export function ControlPlaneApp() {
  return <DevicesPage renderShell={(toolbar, content) => <ControlPlaneShell
    activePage="devices"
    title="Device workspace"
    description="Select a target, choose how FSQ should test it, and follow real evidence while the run progresses."
    titleActions={toolbar}
  >{content}</ControlPlaneShell>} />;
}
