# OpenCode team workflows

Internal OpenCode configuration using our LiteLLM service.

## Setup

Place this repository in `~/.config/opencode/` (back up any existing configuration first). Connect to the configured LiteLLM provider through OpenCode's `/connect` command.

For GitHub work, install and authenticate `gh`. For Azure DevOps, use Azure CLI with the `azure-devops` extension.

## Usage

Open OpenCode from your project's directory:

```sh
opencode
```

### Make a change

Select **architect**. Describe the feature or bug, answer clarifying questions, and choose a branch or worktree when asked. Review and approve the proposed plan, then say **Execute**.

### Court planning

Select **magister** to investigate and plan a change. Magister asks focused
questions when important details are unclear and writes plans to a repository
Markdown file named `court_*.md`. If you explicitly ask for a plan, Magister
writes a draft even when details are still unresolved, recording open questions
and assumptions for follow-up.

Seneschal chooses among three Court developers for each task:
- **magister-developer-high** — high effort, the default for ordinary tasks and for
  complex or uncertain work.
- **magister-developer-mid** — mid effort for well-scoped small tasks.
- **magister-developer-low** — low effort for truly simple work, such as textual
  edits or straightforward fixes with an obvious approach.

All three retain the same Court approval, testing and reporting safeguards.
Switching tiers does not reset a task's retry limit.

You can explicitly override Court plan-approval gates at any time, including
required reviews, blocker resolution, or separate revision/digest approval.
Magister records and passes the override to Seneschal without asking for the
waived approval again. Execution and Git authorization remain separate unless
your instruction explicitly includes them; tool permissions still apply.

In either workflow, commits, pushes, and pull requests require your explicit authorization.

### Run in Docker

With Docker Compose installed, open this configuration repository:

1. Create `.env` from [`.env.example`](.env.example) if it does not already exist. Set `HOME` to your home directory and choose a server password instead of the example value.
2. Keep your projects in `~/repositories`, or update the project mount in [`compose.yaml`](compose.yaml).
3. Start the server:

```sh
docker compose up -d --build
```

From your project's directory, connect using the password from `.env`:

```sh
OPENCODE_PASSWORD='<your server password>' opencode --server http://127.0.0.1:49374
```

Select **architect** or **magister** in OpenCode as described above. To stop the server, run `docker compose down` from this configuration repository.

### Container Python environments and package access

The Alpine container uses musl-compatible Python interpreters in `/opt/uv/bin`.
Host virtual environments may contain glibc interpreters or incompatible native
extensions. Compose sets `UV_PROJECT_ENVIRONMENT=.venv-opencode`, so each
project/workspace uses a separate container environment without replacing its
host `.venv`. Ignore `.venv-opencode/` in your project repositories.

For private packages, create a short-expiry Azure DevOps PAT for the selected
organization with **Packaging > Read** only. Add it to your local `.env` as
`UV_INDEX_AZURE_FEED_PASSWORD`; Compose supplies the nonsecret username
`VssSessionToken`. This matches the project index name `azure-feed`. For another
index name, use its corresponding `UV_INDEX_<NAME>_USERNAME/PASSWORD` variables.
Direct index credentials do not require Azure CLI login or a keyring provider.
A personal PAT can read feeds your identity can access; it is not a single-feed
credential. Revoke or replace it when expired and recreate the service.

After rebuilding/recreating the container, provision each project explicitly
(substitute its container path and required Python version):

```sh
docker compose exec -w /home/reinder/repositories/ctk/ctk-redcap-schema opencode \
  uv sync --locked --python /opt/uv/bin/python3.14
```

Agents can then run `uv run --no-sync` checks. Initial provisioning may download
packages and execute package build code; it requires your authorization. Normal
checks must not silently sync or repair environments.

### Shared encrypted keyring

The image installs `keyring` with `keyrings.cryptfile` and explicitly selects
`CryptFileKeyring`; no plaintext fallback or privileged container is configured.
The encrypted store persists at
`~/.local/share/opencode/keyring/cryptfile_pass.cfg` in the mounted OpenCode data
directory. It uses Argon2 key derivation and authenticated AES-GCM encryption;
service/user identifiers are not encrypted. Back up the encrypted file securely.

Set a strong, unique `KEYRING_CRYPTFILE_PASSWORD` in your local `.env` and restrict
that file's permissions (`chmod 600 .env`). Keep the password separate from
encrypted-file backups. Missing/empty unlock passwords are not usable for
noninteractive access; the first store initialization is interactive. Never
share the real password or PAT with an agent in chat.

Rebuild/recreate the service after changing Docker or environment settings:

```sh
docker compose up -d --build
```

Store a secret from your own terminal, not through agent execution. On first use
the backend asks you to set and confirm the keyring password: use the same value
as `KEYRING_CRYPTFILE_PASSWORD`. The CLI then prompts for the secret itself.

```sh
docker compose exec opencode keyring set example-service example-user
```

Use stable service/user names for future integrations. Programs retrieve secrets
through a compatible keyring API or the container CLI and should pass them
directly to consumers, never print them. Project Python environments do not
automatically inherit the image's keyring Python packages; the installed CLI is
shared. `keyring get` writes the secret to stdout, so do not run it as an agent
diagnostic. Serialize store mutations; this file backend is not a concurrent
multi-writer secret server. Package credentials above are independent of this
store, so existing `uv` authentication does not depend on initializing it.

**Security boundary:** every agent and subprocess in this container can access
the package PAT, unlock password and all unlocked keyring secrets. Encryption
protects the file at rest, not secrets from running agents; it does not provide
per-agent isolation. Docker administrators can inspect container environment
variables. Avoid importing a broad personal Azure login just for package reads.
Existing host cache/repository mounts remain writable and are not hardened by
this configuration.

## Maintenance

For configuration maintainers: install `just` and CUE, edit `cue/` rather than generated `opencode.json`, then run:

```sh
just validate
just build
```

Include the regenerated `opencode.json` with configuration changes.
