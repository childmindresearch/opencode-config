"""Print Azure APIM models excluding known specialized endpoints as CUE-ready JSON.

Requires a gateway that exposes GET /models. Use AZURE_APIM_TOKEN or
retrieve a key through your existing Azure CLI login. No files are changed.
Vision-input LLMs and legacy completion models are included. Specialized media,
speech, OCR, embedding, ranking, and router endpoints are excluded. Classification
uses model names, not verified gateway capabilities; unknown IDs are warned about
on stderr and retained. Use --all-models to inspect the unfiltered list.
"""

import argparse
import email.message
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Final, IO

BASE_URL: Final = "https://cmi-apim-01.azure-api.net/CMI-APIM/openai"
PROVIDER: Final = "azureapim"
EXCLUDED_MODEL_PATTERN: Final = re.compile(
    r"(?:^|[-_.])(?:embed(?:ding)?|rerank|parse|ocr|document-ai|search|similarity|"
    r"audio|speech|tts|whisper|transcribe|realtime|live|image|moderation|"
    r"flux|stable-diffusion|sora|dall-e|model-router)(?:$|[-_.])",
    re.IGNORECASE,
)
# Match language-generating families, not entire vendors that also offer media models.
LLM_MODEL_PATTERN: Final = re.compile(
    r"(?:ai21-jamba|codestral|cohere-command|deepseek-[rv]\d+(?:\.\d+)*|"
    r"kimi-k\d+(?:\.\d+)*|(?:meta-)?llama-\d+(?:\.\d+)*|"
    r"mai-(?:code|ds-r1|thinking|\d+b|m365)|ministral-\d+b|"
    r"mistral-(?:large|medium|small|nemo)|nemotron-\d+|phi-\d+(?:\.\d+)*|"
    r"claude-(?:haiku|sonnet|opus)|(?:text-)?(?:ada|babbage|curie|davinci)|"
    r"code-(?:cushman|davinci)|codex-mini|computer-use-preview|"
    r"gpt-(?:\d+(?:\.\d+)*(?:o)?|chat-latest|oss-\d+b)|"
    r"grok-\d+(?:\.\d+)*|jais-\d+b-chat|o[134]|qwen-?\d+(?:\.\d+)*)"
    r"(?:$|-)",
    re.IGNORECASE,
)


def fetch_subscription_key(
    resource_group: str,
    service_name: str,
    apim_subscription_id: str,
    azure_subscription_id: str | None,
) -> str:
    """Read an existing APIM subscription's primary key via Azure CLI.

    Requires Azure RBAC permission to list subscription secrets. This does not
    create subscriptions or regenerate keys.
    """
    subscription = (
        urllib.parse.quote(azure_subscription_id, safe="")
        if azure_subscription_id
        else "{subscriptionId}"
    )
    resource_group, service_name, apim_subscription_id = (
        urllib.parse.quote(value, safe="")
        for value in (resource_group, service_name, apim_subscription_id)
    )
    url = (
        f"/subscriptions/{subscription}/resourceGroups/{resource_group}"
        f"/providers/Microsoft.ApiManagement/service/{service_name}"
        f"/subscriptions/{apim_subscription_id}/listSecrets?api-version=2024-05-01"
    )
    try:
        result = subprocess.run(
            [
                "az",
                "rest",
                "--method",
                "post",
                "--url",
                url,
                "--query",
                "primaryKey",
                "--output",
                "json",
                "--only-show-errors",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError as error:
        raise SystemExit(
            "Azure CLI is missing. Install az and run az login, or set AZURE_APIM_TOKEN."
        ) from error
    except subprocess.TimeoutExpired as error:
        raise SystemExit("Azure CLI key retrieval timed out.") from error
    if result.returncode:
        # Do not echo CLI output: it may contain sensitive response details.
        raise SystemExit(
            f"Azure CLI key retrieval failed (exit {result.returncode}). "
            "Check az login, the resource IDs, and your permission to list APIM subscription secrets."
        )
    try:
        key = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise SystemExit("Azure CLI returned invalid JSON for the APIM key.") from error
    if not isinstance(key, str) or not key.strip():
        raise SystemExit("Azure CLI did not return a non-empty APIM primary key.")
    return key.strip()


def list_models(base_url: str, subscription_key: str) -> list[str]:
    """Fetch model IDs exposed by the gateway, failing on incomplete results."""
    parsed_url = urllib.parse.urlsplit(base_url)
    if (
        parsed_url.scheme != "https"
        or not parsed_url.netloc
        or parsed_url.username is not None
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise SystemExit(
            "--base-url must be an HTTPS base URL without credentials, query, or fragment."
        )
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/models",
        headers={
            "Ocp-Apim-Subscription-Key": subscription_key,
            "Accept": "application/json",
        },
    )
    # Do not forward a subscription key to a redirect destination.
    opener = urllib.request.build_opener(NoRedirectHandler())
    try:
        with opener.open(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        hint = {
            401: "Check AZURE_APIM_TOKEN and the gateway's authentication policy.",
            403: "Check AZURE_APIM_TOKEN and the subscription's access to this API.",
            404: "The gateway may not expose /models; ask its administrator about model discovery.",
            405: "The gateway may not support GET /models; ask its administrator about model discovery.",
        }.get(error.code, "Check the gateway endpoint and its policies.")
        error.close()
        raise SystemExit(
            f"APIM model discovery failed (HTTP {error.code}). {hint}"
        ) from error
    except urllib.error.URLError as error:
        raise SystemExit(
            f"Could not reach the APIM model endpoint: {error.reason}"
        ) from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SystemExit("APIM /models did not return valid JSON.") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise SystemExit(
            "Expected an OpenAI-compatible /models response with a 'data' list."
        )
    if payload.get("has_more") or payload.get("next_link") or payload.get("nextLink"):
        raise SystemExit(
            "The gateway returned paginated results; refusing to print an incomplete model list."
        )
    model_ids: set[str] = set()
    for model in payload["data"]:
        if (
            not isinstance(model, dict)
            or not isinstance(model.get("id"), str)
            or not model["id"].strip()
        ):
            raise SystemExit(
                "Every entry in APIM /models must have a non-empty string 'id'."
            )
        model_ids.add(model["id"])
    return sorted(model_ids)


def is_llm_model_id(model_id: str) -> bool:
    """Return whether an ID should be kept in the text-oriented model list.

    OpenAI-compatible /models responses commonly expose only IDs, not model
    capabilities. Exclusions take precedence over family matches, so GPT speech
    and image endpoints cannot leak into the result. Unknown families are retained;
    this does not establish chat, tool-calling, or OpenCode compatibility.
    """
    return EXCLUDED_MODEL_PATTERN.search(model_id) is None


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects so gateway credentials cannot be forwarded elsewhere."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: email.message.Message,
        newurl: str,
    ) -> None:
        """Leave redirect responses to the normal HTTP error handler."""
        return None


def main() -> None:
    """Print selected gateway models as entries for the CUE APIM model list."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help="APIM OpenAI API base URL (without /models)",
    )
    parser.add_argument(
        "--resource-group", help="Resource group containing the APIM service"
    )
    parser.add_argument(
        "--service-name",
        default="cmi-apim-01",
        help="APIM service name (default: %(default)s)",
    )
    parser.add_argument(
        "--apim-subscription-id",
        help="APIM subscription resource ID, not the Azure subscription ID",
    )
    parser.add_argument(
        "--azure-subscription-id",
        help="Azure subscription UUID (default: Azure CLI's current subscription)",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--llm-only",
        dest="llm_only",
        action="store_true",
        default=True,
        help="exclude known specialized endpoints, retaining unknown models (default)",
    )
    selection.add_argument(
        "--all-models",
        dest="llm_only",
        action="store_false",
        help="print every gateway model without classification",
    )
    args = parser.parse_args()
    subscription_key = os.environ.get("AZURE_APIM_TOKEN", "").strip()
    if not subscription_key:
        if not args.resource_group or not args.apim_subscription_id:
            parser.error(
                "set AZURE_APIM_TOKEN or provide --resource-group and --apim-subscription-id for Azure CLI retrieval"
            )
        subscription_key = fetch_subscription_key(
            args.resource_group,
            args.service_name,
            args.apim_subscription_id,
            args.azure_subscription_id,
        )
    model_ids = list_models(args.base_url, subscription_key)
    if args.llm_only:
        for model_id in model_ids:
            if is_llm_model_id(model_id) and not LLM_MODEL_PATTERN.match(model_id):
                print(
                    f"Warning: retaining unclassified model ID {model_id!r}; "
                    "its capabilities have not been verified.",
                    file=sys.stderr,
                )
        model_ids = [model_id for model_id in model_ids if is_llm_model_id(model_id)]
    models = [
        {"id": model_id, "name": f"Azure APIM {model_id}", "provider": PROVIDER}
        for model_id in model_ids
    ]
    print(json.dumps(models, indent=4, sort_keys=True))


if __name__ == "__main__":
    main()
