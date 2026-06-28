import json
import os
import urllib.error
import urllib.request

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-3-5"
SYSTEM_PROMPT = (
    "You are a code documentation assistant. Given a code snippet, return ONLY a single sentence "
    "(max 20 words) describing what the code does. No preamble, no explanation, just the one sentence."
)


# Builds the standard API Gateway response with CORS headers.
def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "OPTIONS,POST",
        },
        "body": json.dumps(body),
    }


# Calls Anthropic Messages API with urllib and returns the generated text.
def call_anthropic(code, language):
    api_key = os.environ["ANTHROPIC_API_KEY"]
    payload = {
        "model": MODEL,
        "max_tokens": 100,
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": f"Language: {language}\n\nCode:\n{code}",
            }
        ],
    }
    request = urllib.request.Request(
        ANTHROPIC_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as result:
        data = json.loads(result.read().decode("utf-8"))
        return data["content"][0]["text"].strip()


# Handles API Gateway events and returns a one-line AI summary for submitted code.
def lambda_handler(event, context):
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return response(204, {})

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return response(400, {"error": "Invalid JSON body"})

    code = str(body.get("code", "")).strip()
    language = str(body.get("language", "plaintext")).strip() or "plaintext"

    if not code:
        return response(400, {"error": "Code is required"})

    try:
        summary = call_anthropic(code, language)
        return response(200, {"summary": summary})
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        return response(exc.code, {"error": "Anthropic API request failed", "detail": detail})
    except Exception as exc:
        return response(500, {"error": str(exc)})
