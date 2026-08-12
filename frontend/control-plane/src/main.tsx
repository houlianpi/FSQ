import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { ControlPlaneApp } from './app/ControlPlaneApp';
import './styles/tokens.css';
import './styles/devices.css';
import './styles/config.css';

const root = document.getElementById('root');
if (!root) throw new Error('Control Plane root element was not found.');
createRoot(root).render(<StrictMode><ControlPlaneApp /></StrictMode>);
