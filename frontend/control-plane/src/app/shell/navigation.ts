export type ControlPlanePageId = 'overview' | 'workspace' | 'devices' | 'runs' | 'config' | 'settings';
export type NavigationIcon = 'overview' | 'workspace' | 'devices' | 'runs' | 'config' | 'settings';

export interface NavigationItem {
  id: ControlPlanePageId;
  label: string;
  icon: NavigationIcon;
  available: boolean;
  section: 'primary' | 'footer';
}

export const CONTROL_PLANE_NAVIGATION: readonly NavigationItem[] = [
  { id: 'overview', label: 'Overview', icon: 'overview', available: false, section: 'primary' },
  { id: 'workspace', label: 'Workspace', icon: 'workspace', available: false, section: 'primary' },
  { id: 'devices', label: 'Devices', icon: 'devices', available: true, section: 'primary' },
  { id: 'runs', label: 'Runs', icon: 'runs', available: false, section: 'primary' },
  { id: 'config', label: 'Config', icon: 'config', available: false, section: 'footer' },
  { id: 'settings', label: 'Settings', icon: 'settings', available: false, section: 'footer' },
] as const;

export interface WorkspaceNavigationItem {
  id: string;
  label: string;
  description?: string;
  available?: boolean;
}
