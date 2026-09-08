import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PreflightStatus } from './PreflightStatus';
import type { ReadinessResponse } from '../../../api/types';

const ok={status:'ready' as const,message:'Ready',action:''};
const mac:ReadinessResponse={workspaceName:'test',platformId:'macos',workspace:ok,platform:ok,provider:ok,target:ok,strict:ok,prerequisites:[],commands:{caseCreate:ok,caseTest:ok},checkedAt:'2026-09-07T00:00:00Z'};

it('distinguishes a failed diagnostic request from a missing installation and permits retry',async()=>{
  const recheck=vi.fn();
  render(<PreflightStatus macos mode="explore" loading={false} diagnostics={null} onRecheck={recheck}/>);
  expect(screen.getByRole('status')).toHaveTextContent('Environment check unavailable');
  expect(screen.queryByText('Appium CLI')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button',{name:'Recheck environment'}));
  expect(recheck).toHaveBeenCalledTimes(1);
});

it('renders the packaged setup guide on disclosure without a network request',async()=>{
  render(<PreflightStatus macos mode="explore" loading={false} diagnostics={mac}/>);
  const summary=screen.getByText('macOS installation and troubleshooting');
  expect(summary.parentElement).not.toHaveAttribute('open');
  await userEvent.click(summary);
  expect(summary.parentElement).toHaveAttribute('open');
  expect(screen.getByText(/Install full Xcode from the Mac App Store/)).toBeVisible();
});
