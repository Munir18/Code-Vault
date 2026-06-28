import json
import os

import pymysql
from pymysql.cursors import DictCursor


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


# Opens a PyMySQL connection using Lambda environment variables.
def get_connection():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ.get("DB_NAME", "snippetvault"),
        cursorclass=DictCursor,
        autocommit=False,
        charset="utf8mb4",
    )


# Converts submitted tags into a clean lowercase list without duplicates.
def normalize_tags(tags):
    if tags is None:
        return []
    if isinstance(tags, str):
        tags = tags.split(",")
    cleaned = []
    for tag in tags:
        value = str(tag).strip().lower()
        if value and value not in cleaned:
            cleaned.append(value)
    return cleaned


# Creates missing tag rows and links them to the new snippet.
def attach_tags(cursor, snippet_id, tags):
    for tag in normalize_tags(tags):
        cursor.execute(
            "INSERT INTO tags (name) VALUES (%s) ON DUPLICATE KEY UPDATE name = VALUES(name)",
            (tag,),
        )
        cursor.execute("SELECT id FROM tags WHERE name = %s", (tag,))
        tag_row = cursor.fetchone()
        cursor.execute(
            "INSERT IGNORE INTO snippet_tags (snippet_id, tag_id) VALUES (%s, %s)",
            (snippet_id, tag_row["id"]),
        )


# Handles API Gateway events and writes a snippet to RDS MySQL.
def lambda_handler(event, context):
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return response(204, {})

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return response(400, {"success": False, "error": "Invalid JSON body"})

    title = str(body.get("title", "")).strip()
    code = str(body.get("code", "")).strip()
    language = str(body.get("language", "plaintext")).strip().lower() or "plaintext"
    user_id = body.get("user_id", 1)

    if not title or not code:
        return response(400, {"success": False, "error": "Title and code are required"})

    connection = None
    try:
        connection = get_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO snippets (user_id, title, code, language)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, title, code, language),
            )
            snippet_id = cursor.lastrowid
            attach_tags(cursor, snippet_id, body.get("tags", []))
            connection.commit()
            return response(201, {"success": True, "snippet_id": snippet_id})
    except Exception as exc:
        if connection:
            connection.rollback()
        return response(500, {"success": False, "error": str(exc)})
    finally:
        if connection:
            connection.close()
