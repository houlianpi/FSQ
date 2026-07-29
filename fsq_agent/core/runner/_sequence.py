# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from collections.abc import Sequence

from fsq_agent.core.evidence import EvidenceRecorder
from fsq_agent.core.runner._runner import StepRunner
from fsq_agent.models import EvidenceBundle, ExecutableStep


_STOP_STATUSES = {"failed", "cancelled", "skipped"}


class _StepSequenceFailure(Exception):
    pass


class StepSequenceRunner:
    def __init__(
        self,
        step_runner: StepRunner,
        evidence_recorder: EvidenceRecorder,
    ) -> None:
        self.step_runner = step_runner
        self.evidence_recorder = evidence_recorder

    def run_steps(
        self,
        run_id: str,
        steps: Sequence[ExecutableStep],
        teardown_steps: Sequence[ExecutableStep] = (),
    ) -> EvidenceBundle:
        ran_step = False

        def run_next(step: ExecutableStep):
            nonlocal ran_step
            result = self._run_and_record(run_id, step)
            ran_step = True
            return result

        try:
            for step in steps:
                result = run_next(step)
                if result.status in _STOP_STATUSES:
                    raise _StepSequenceFailure
        except _StepSequenceFailure:
            pass
        finally:
            for step in teardown_steps:
                run_next(step)
        return self.evidence_recorder.build_bundle()

    def _run_and_record(self, run_id: str, step: ExecutableStep):
        result = self.step_runner.run_step(run_id=run_id, step=step)
        for event in self.step_runner.events:
            self.evidence_recorder.record_event(event)
        self.evidence_recorder.record_step_result(result)
        return result
