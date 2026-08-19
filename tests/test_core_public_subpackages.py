# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import importlib

from fsq_agent import core
from fsq_agent.core import evidence, interfaces, runner


def test_core_root_reexports_canonical_subpackage_objects() -> None:
    assert core.StepRunner is runner.StepRunner
    assert core.StepSequenceRunner is runner.StepSequenceRunner
    assert core.ArtifactStore is evidence.ArtifactStore
    assert core.EvidenceRecorder is evidence.EvidenceRecorder
    assert core.HarnessInterface is interfaces.HarnessInterface
    assert core.DriverFactory is interfaces.DriverFactory
    assert core.HarnessFactory is interfaces.HarnessFactory
    assert isinstance(core.CapabilityRegistry(), interfaces.CapabilityRegistryInterface)
    assert isinstance(core.RuntimeSecretStore.empty(), interfaces.RuntimeSecretResolver)


def test_harness_protocol_compatibility_modules_alias_canonical_modules() -> None:
    pairs = [
        ("fsq_agent.core.harness._interface", "fsq_agent.core.interfaces._harness"),
        ("fsq_agent.core.harness._android_driver", "fsq_agent.core.interfaces._android_driver"),
        ("fsq_agent.core.harness._web_driver", "fsq_agent.core.interfaces._web_driver"),
        ("fsq_agent.core.harness._windows_driver", "fsq_agent.core.interfaces._windows_driver"),
        ("fsq_agent.core.harness._macos_driver", "fsq_agent.core.interfaces._macos_driver"),
    ]

    for legacy_name, canonical_name in pairs:
        assert importlib.import_module(legacy_name) is importlib.import_module(canonical_name)
