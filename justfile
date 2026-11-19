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

# Check that Docker is available.
_check-docker:
    @command -v docker >/dev/null 2>&1 || { printf '%s\n' "Docker is required to run CUE. Install Docker and rerun just." >&2; exit 1; }
