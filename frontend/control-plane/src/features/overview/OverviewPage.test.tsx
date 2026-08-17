import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { OverviewPage } from './OverviewPage';

it('reproduces the FSQ UX draft Overview and preserves its navigation commands', async () => {
  const onNavigate = vi.fn();
  const user = userEvent.setup();
  render(<OverviewPage onNavigate={onNavigate} />);

  expect(screen.getByRole('heading', { name: 'Start a run' })).toBeVisible();
  expect(screen.getByText('Start with the core loop, follow a guided tutorial, or launch a task on one of your connected devices.')).toBeVisible();
  expect(screen.getByText('01 / DYNAMIC LOOP')).toBeVisible();
  expect(screen.getByText('02 / STRICT LOOP')).toBeVisible();
  expect(screen.getByText('Describe a user-visible goal. FSQ plans, operates your app, captures every step, verifies the result, and drafts a replayable case.')).toBeVisible();
  expect(screen.getByText('Select a reviewed YAML case. FSQ executes authored commands exactly and produces fresh evidence for regression testing.')).toBeVisible();
  expect(screen.getByText('Uses configured LLM')).toBeVisible();
  expect(screen.getByText('No planning LLM')).toBeVisible();
  for (const step of ['Explore', 'Capture', 'Verify', 'Save Case', 'Replay']) expect(screen.getByText(step)).toBeVisible();
  expect(screen.getByText('Turn a human goal into key actions.')).toBeVisible();
  expect(screen.getByText('Record screenshots, UI trees, and tool facts.')).toBeVisible();
  expect(screen.getByText('Judge the goal from evidence, not self-report.')).toBeVisible();
  expect(screen.getByText('Review actual successful actions as YAML.')).toBeVisible();
  expect(screen.getByText('Run deterministically for regression.')).toBeVisible();
  expect(screen.getByRole('heading', { name: 'Recent activity' })).toBeVisible();
  expect(screen.getByText('Evidence from this workspace')).toBeVisible();
  expect(screen.getByText('Create project flow')).toBeVisible();
  expect(screen.getByText('AI explore · Web · 4m ago')).toBeVisible();
  expect(screen.getByText('Checkout smoke')).toBeVisible();
  expect(screen.getByText('Strict replay · Web · 38m ago')).toBeVisible();
  expect(screen.getByText('Settings profile')).toBeVisible();
  expect(screen.getByText('AI explore · macOS · yesterday')).toBeVisible();
  expect(screen.getByText('success')).toBeVisible();
  expect(screen.getByText('failed')).toBeVisible();
  expect(screen.getByText('inconclusive')).toBeVisible();
  expect(screen.getByRole('heading', { name: 'Environment' })).toBeVisible();
  expect(screen.getByText('Ready to run')).toBeVisible();
  expect(screen.getByText('3 / 3')).toBeVisible();
  expect(screen.getByText('GitHub Copilot · authenticated')).toBeVisible();
  expect(screen.getByText('Web · Playwright · Chrome')).toBeVisible();
  expect(screen.getByText('Cases and evidence writable')).toBeVisible();
  expect(screen.getAllByText('ready')).toHaveLength(3);

  const workflow = screen.getByLabelText('FSQ workflow');
  const scrollIntoView = vi.fn();
  Object.defineProperty(workflow, 'scrollIntoView', { configurable: true, value: scrollIntoView });
  await user.click(screen.getByRole('button', { name: 'How FSQ works' }));
  expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'center' });

  await user.click(screen.getByRole('button', { name: /Explore with AI/ }));
  await user.click(screen.getByRole('button', { name: /Replay a Case/ }));
  await user.click(screen.getByRole('button', { name: /Create project flow/ }));
  await user.click(screen.getByRole('button', { name: /Checkout smoke/ }));
  await user.click(screen.getByRole('button', { name: /Settings profile/ }));
  await user.click(screen.getByRole('button', { name: 'Open workspace' }));
  await user.click(screen.getByRole('button', { name: 'Manage config' }));

  expect(onNavigate.mock.calls).toEqual([
    ['devices'], ['devices'], ['devices'], ['devices'], ['devices'], ['workspace'], ['config'],
  ]);
});