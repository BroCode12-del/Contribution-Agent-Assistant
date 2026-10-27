import os
import json
import uuid
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

def validate_probe(response, expected):
    value = response.model_dump()
    metadata = value.get("meterless") or {}
    if not response.choices or response.choices[0].finish_reason != "stop":
        raise ValueError("The provider did not finish its reply.")
    if (response.choices[0].message.content or "").strip() != expected:
        raise ValueError("The response did not match this fresh probe.")
    if metadata.get("from_cache") is not False:
        raise ValueError("Nightshift did not confirm an uncached response.")
    return {"status": "ready", "from_cache": False,
            "routed_model": metadata.get("routed_model"),
            "winning_route": metadata.get("winning_route")}


def main():
    load_dotenv(Path(__file__).with_name(".env"))
    client = OpenAI(
        base_url=os.environ["METERLESS_BASE_URL"], api_key=os.environ["METERLESS_RUNTIME_TOKEN"],
        default_headers={"meterless-app": "student-contribution-demo", "meterless-scope": "user",
                         "meterless-tier-split": "off"}, timeout=90, max_retries=0,
    )
    expected = "ready-" + uuid.uuid4().hex
    # Thinking tokens count against the completion budget on the Nemotron lane.
    response = client.chat.completions.create(
        model=os.environ["METERLESS_MODEL"],
        messages=[{"role": "user", "content": "Reply with exactly this text and nothing else: " + expected}],
        max_tokens=4096,
    )
    print(json.dumps(validate_probe(response, expected), indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        from run_opportunities import provider_error
        print(json.dumps({"status": "not_verified", "error": provider_error(error)}, indent=2))
        raise SystemExit(1)
