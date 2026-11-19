cue_image := "cuelang/cue:0.17.1"
cue := 'docker run --rm --user "$(id -u):$(id -g)" --mount "type=bind,source=$PWD,target=/workspace" --workdir /workspace ' + cue_image

# Show available commands.
help:
    @just --list

# Generate opencode.json from the CUE source.
build: _check-docker
    {{cue}} export ./cue --out json -o opencode.json --force

# Validate the CUE source.
validate: _check-docker
    {{cue}} vet ./cue

# Generate the agent workflow SVG using TALA.
diagram:
    d2 --layout=tala agents.d2 agents.svg

# Checks the existing artifact; intentionally does not rebuild it.
test:
    node --test scripts/test-config.mjs

# Remove the generated opencode.json.
clean:
    rm -f opencode.json

# Check that Docker is available.
_check-docker:
    @command -v docker >/dev/null 2>&1 || { printf '%s\n' "Docker is required to run CUE. Install Docker and rerun just." >&2; exit 1; }
