import subprocess
from dataclasses import replace

from databricks.bundles.core import Bundle, job_mutator, pipeline_mutator
from databricks.bundles.jobs import Job
from databricks.bundles.pipelines import Pipeline


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


@pipeline_mutator
def tag_pipeline(bundle: Bundle, pipeline: Pipeline) -> Pipeline:
    tags = {**(bundle.resolve_variable(pipeline.tags) or {})}
    tags["git_sha"] = _git_sha()
    return replace(pipeline, tags=tags)


@job_mutator
def tag_job(bundle: Bundle, job: Job) -> Job:
    tags = {**(bundle.resolve_variable(job.tags) or {})}
    tags["git_sha"] = _git_sha()
    return replace(job, tags=tags)
