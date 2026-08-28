# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from fsq_agent import application
from fsq_agent.application import _contracts as legacy_contracts
from fsq_agent.application import cases, contracts, environments, providers, runs, workspace


def test_resource_modules_export_the_package_public_objects() -> None:
    assert cases.create_case is application.create_case
    assert cases.test_case is application.test_case
    assert runs.list_runs is application.list_runs
    assert runs.show_run is application.show_run
    assert runs.read_run_logs is application.read_run_logs
    assert providers.configure_azure_openai is application.configure_azure_openai
    assert providers.request_github_device_code is application.request_github_device_code
    assert providers.complete_github_configuration is application.complete_github_configuration
    assert providers.provider_status is application.provider_status
    assert environments.list_environments is application.list_environments
    assert workspace.require_initialized_workspace is application.require_initialized_workspace
    assert workspace.initialize_workspace is application.initialize_workspace


def test_legacy_contract_module_forwards_canonical_type_identity() -> None:
    for name in contracts.__all__:
        assert getattr(legacy_contracts, name) is getattr(contracts, name)
        assert getattr(application, name) is getattr(contracts, name)
