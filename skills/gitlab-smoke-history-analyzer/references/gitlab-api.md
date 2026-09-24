# GitLab API Acquisition

Use the GitLab REST API only with an existing authorized token. Keep the token in an environment variable and never print it.

## Required Inputs

- API base URL, such as `https://gitlab.example.com/api/v4`.
- URL-encoded project path or numeric project ID.
- branch name or explicit commit SHAs.
- an access token supplied as `GITLAB_TOKEN`.

## Read-Only Endpoints

```text
GET /projects/:id/pipelines?ref=:branch
GET /projects/:id/pipelines/:pipeline_id/jobs
GET /projects/:id/jobs/:job_id/artifacts
GET /projects/:id/jobs/:job_id/trace
```

Download artifact archives under an ignored evidence root. Save a small metadata manifest beside each archive containing pipeline ID, job ID, commit SHA, job name, status, runner description, and retrieval time. This makes offline analysis reproducible.

