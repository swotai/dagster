# pylint doesn't know about pytest fixtures
# pylint: disable=unused-argument

import os
import time

from dagster.core.storage.pipeline_run import PipelineRunStatus
from dagster.core.test_utils import create_run_for_test, poll_for_finished_run
from dagster.utils import merge_dicts
from dagster.utils.yaml_utils import merge_yamls
from dagster_k8s.job import get_job_name_from_run_id
from dagster_k8s.utils import delete_job
from dagster_k8s_test_infra.helm import TEST_AWS_CONFIGMAP_NAME
from dagster_k8s_test_infra.integration_utils import image_pull_policy
from dagster_test.test_project import (
    ReOriginatedExternalPipelineForTest,
    get_test_project_environments_path,
    get_test_project_workspace_and_external_pipeline,
)

IS_BUILDKITE = os.getenv("BUILDKITE") is not None


def log_run_events(instance, run_id):
    for log in instance.all_logs(run_id):
        print(str(log) + "\n")  # pylint: disable=print-call


def get_celery_job_engine_config(dagster_docker_image, job_namespace):
    return {
        "execution": {
            "config": merge_dicts(
                (
                    {
                        "job_image": dagster_docker_image,
                    }
                    if dagster_docker_image
                    else {}
                ),
                {
                    "job_namespace": job_namespace,
                    "image_pull_policy": image_pull_policy(),
                    "env_config_maps": ["dagster-pipeline-env"]
                    + ([TEST_AWS_CONFIGMAP_NAME] if not IS_BUILDKITE else []),
                },
            )
        },
    }


def get_failing_celery_job_engine_config(dagster_docker_image, job_namespace):
    return {
        "execution": {
            "config": merge_dicts(
                (
                    {
                        "job_image": dagster_docker_image,
                    }
                    if dagster_docker_image
                    else {}
                ),
                {
                    "job_namespace": job_namespace,
                    "image_pull_policy": image_pull_policy(),
                    "env_config_maps": [] + ([TEST_AWS_CONFIGMAP_NAME] if not IS_BUILDKITE else []),
                },
            )
        },
    }


def test_run_monitoring_fails_on_interrupt(  # pylint: disable=redefined-outer-name
    dagster_docker_image, dagster_instance, helm_namespace
):
    run_config = merge_dicts(
        merge_yamls(
            [
                os.path.join(get_test_project_environments_path(), "env.yaml"),
                os.path.join(get_test_project_environments_path(), "env_s3.yaml"),
            ]
        ),
        get_celery_job_engine_config(
            dagster_docker_image=dagster_docker_image, job_namespace=helm_namespace
        ),
    )

    pipeline_name = "demo_job_celery"
    with get_test_project_workspace_and_external_pipeline(dagster_instance, pipeline_name) as (
        workspace,
        external_pipeline,
    ):
        reoriginated_pipeline = ReOriginatedExternalPipelineForTest(external_pipeline)

        run = create_run_for_test(
            dagster_instance,
            pipeline_name=pipeline_name,
            run_config=run_config,
            mode="default",
            external_pipeline_origin=reoriginated_pipeline.get_external_origin(),
            pipeline_code_origin=reoriginated_pipeline.get_python_origin(),
        )

        try:
            dagster_instance.launch_run(run.run_id, workspace)

            start_time = time.time()
            while time.time() - start_time < 60:
                run = dagster_instance.get_run_by_id(run.run_id)
                if run.status == PipelineRunStatus.STARTED:
                    break
                assert run.status == PipelineRunStatus.STARTING
                time.sleep(1)

            assert delete_job(get_job_name_from_run_id(run.run_id), helm_namespace)

            poll_for_finished_run(dagster_instance, run.run_id, timeout=120)
            assert dagster_instance.get_run_by_id(run.run_id).status == PipelineRunStatus.FAILURE
        finally:
            log_run_events(dagster_instance, run.run_id)


def test_run_monitoring_startup_fail(  # pylint: disable=redefined-outer-name
    dagster_docker_image, dagster_instance, helm_namespace
):
    run_config = merge_dicts(
        merge_yamls(
            [
                os.path.join(get_test_project_environments_path(), "env.yaml"),
                os.path.join(get_test_project_environments_path(), "env_s3.yaml"),
            ]
        ),
        get_failing_celery_job_engine_config(
            dagster_docker_image=dagster_docker_image, job_namespace=helm_namespace
        ),
    )

    pipeline_name = "demo_job_celery"
    with get_test_project_workspace_and_external_pipeline(dagster_instance, pipeline_name) as (
        workspace,
        external_pipeline,
    ):
        reoriginated_pipeline = ReOriginatedExternalPipelineForTest(external_pipeline)

        run = create_run_for_test(
            dagster_instance,
            pipeline_name=pipeline_name,
            run_config=run_config,
            mode="default",
            external_pipeline_origin=reoriginated_pipeline.get_external_origin(),
            pipeline_code_origin=reoriginated_pipeline.get_python_origin(),
        )

        try:
            dagster_instance.launch_run(run.run_id, workspace)

            poll_for_finished_run(dagster_instance, run.run_id, timeout=120)
            assert dagster_instance.get_run_by_id(run.run_id).status == PipelineRunStatus.FAILURE
        finally:
            log_run_events(dagster_instance, run.run_id)
