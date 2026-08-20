# Understanding-GPU

## Cursor Cloud specific instructions

### Current repository state

As of this environment setup, the repository contains only `README.md` (title `# Understanding-GPU`). There is:

- No application code
- No dependency manifests (no `package.json`, `requirements.txt`, `pyproject.toml`, etc.)
- No tests, linters, or build system
- No services to run

There is therefore nothing to lint, test, build, or run yet. Do not fabricate an application; wait for real code to be added.

### Available toolchains

The base VM already provides:

- Node.js `v22.14.0` (with `npm`; use `corepack enable` if `pnpm`/`yarn` are later adopted)
- Python `3.12.3` (with `pip`)

### When code is added

The update script is intentionally minimal and guarded. It automatically installs dependencies only if the corresponding manifest appears:

- `package-lock.json` -> `npm ci`; otherwise `package.json` -> `npm install`
- `requirements.txt` -> `pip install -r requirements.txt`

If the project adopts a different stack or package manager (e.g. `pnpm`, `uv`, CUDA/`nvcc` toolchains, a Dockerfile), update the SetupVmEnvironment update script and revise this section with the real lint/test/build/run commands. The repo name suggests GPU-related work; note that a GPU is not guaranteed to be present in the Cloud Agent VM, so document any CPU-only fallbacks here when relevant.
