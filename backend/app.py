import os
from contextlib import contextmanager

import pymysql
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymysql.cursors import DictCursor

load_dotenv()

app = Flask(__name__)
CORS(app)


# Reads database settings from environment variables and returns a PyMySQL config dictionary.
def db_config():
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER", "snippetvault"),
        "password": os.getenv("DB_PASSWORD", "snippetvault"),
        "database": os.getenv("DB_NAME", "snippetvault"),
        "cursorclass": DictCursor,
        "autocommit": False,
        "charset": "utf8mb4",
    }


# Opens a database connection and always closes it after the request work completes.
@contextmanager
def get_connection():
    connection = pymysql.connect(**db_config())
    try:
        yield connection
    finally:
        connection.close()


# Converts a comma-separated string or JSON list into a clean list of unique tag names.
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


# Returns a consistent JSON error response with an HTTP status code.
def error_response(message, status_code=400):
    return jsonify({"error": message}), status_code


# Creates missing tags and links the supplied tags to a snippet inside the current transaction.
def replace_snippet_tags(cursor, snippet_id, tags):
    cursor.execute("DELETE FROM snippet_tags WHERE snippet_id = %s", (snippet_id,))
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


# Fetches all tags attached to the provided snippet id.
def get_tags_for_snippet(cursor, snippet_id):
    cursor.execute(
        """
        SELECT t.name
        FROM tags t
        JOIN snippet_tags st ON st.tag_id = t.id
        WHERE st.snippet_id = %s
        ORDER BY t.name
        """,
        (snippet_id,),
    )
    return [row["name"] for row in cursor.fetchall()]


# Confirms the API and container are running.
@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


# Returns public snippets with optional full-text search, language filter, and tag filter.
@app.get("/api/snippets")
def list_snippets():
    search = request.args.get("search", "").strip()
    tag = request.args.get("tag", "").strip().lower()
    language = request.args.get("language", "").strip().lower()

    conditions = ["s.is_public = TRUE"]
    params = []
    joins = [
        "LEFT JOIN snippet_tags st ON st.snippet_id = s.id",
        "LEFT JOIN tags t ON t.id = st.tag_id",
    ]

    if search:
        conditions.append("MATCH(s.title, s.code, s.description) AGAINST (%s IN NATURAL LANGUAGE MODE)")
        params.append(search)
    if tag:
        conditions.append(
            """
            EXISTS (
                SELECT 1
                FROM snippet_tags filter_st
                JOIN tags filter_t ON filter_t.id = filter_st.tag_id
                WHERE filter_st.snippet_id = s.id AND filter_t.name = %s
            )
            """
        )
        params.append(tag)
    if language:
        conditions.append("LOWER(s.language) = %s")
        params.append(language)

    query = f"""
        SELECT
            s.id,
            s.title,
            s.language,
            s.code,
            s.created_at,
            GROUP_CONCAT(DISTINCT t.name ORDER BY t.name SEPARATOR ',') AS tags
        FROM snippets s
        {' '.join(joins)}
        WHERE {' AND '.join(conditions)}
        GROUP BY s.id, s.title, s.language, s.code, s.created_at
        ORDER BY s.created_at DESC
    """

    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                snippets = cursor.fetchall()
                for snippet in snippets:
                    snippet["tags"] = snippet["tags"].split(",") if snippet["tags"] else []
                    snippet["created_at"] = snippet["created_at"].isoformat()
                return jsonify(snippets)
    except Exception as exc:
        return error_response(f"Failed to fetch snippets: {exc}", 500)


# Returns one snippet with its full code and tags.
@app.get("/api/snippets/<int:snippet_id>")
def get_snippet(snippet_id):
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM snippets WHERE id = %s", (snippet_id,))
                snippet = cursor.fetchone()
                if not snippet:
                    return error_response("Snippet not found", 404)
                snippet["tags"] = get_tags_for_snippet(cursor, snippet_id)
                snippet["created_at"] = snippet["created_at"].isoformat()
                snippet["updated_at"] = snippet["updated_at"].isoformat()
                return jsonify(snippet)
    except Exception as exc:
        return error_response(f"Failed to fetch snippet: {exc}", 500)


# Creates a snippet and links any submitted tags.
@app.post("/api/snippets")
def create_snippet():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    code = str(data.get("code", "")).strip()
    language = str(data.get("language", "plaintext")).strip().lower() or "plaintext"
    user_id = data.get("user_id", 1)
    description = data.get("description")
    ai_summary = data.get("ai_summary")

    if not title or not code:
        return error_response("Title and code are required")

    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO snippets (user_id, title, code, language, description, ai_summary)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (user_id, title, code, language, description, ai_summary),
                )
                snippet_id = cursor.lastrowid
                replace_snippet_tags(cursor, snippet_id, data.get("tags", []))
                connection.commit()
                return jsonify({"id": snippet_id}), 201
    except Exception as exc:
        return error_response(f"Failed to create snippet: {exc}", 500)


# Updates an existing snippet and replaces its tag links when tags are provided.
@app.put("/api/snippets/<int:snippet_id>")
def update_snippet(snippet_id):
    data = request.get_json(silent=True) or {}
    allowed_fields = ["title", "code", "language", "description", "ai_summary"]
    updates = []
    params = []

    for field in allowed_fields:
        if field in data:
            updates.append(f"{field} = %s")
            value = data[field]
            if field == "language":
                value = str(value).strip().lower() or "plaintext"
            params.append(value)

    if not updates and "tags" not in data:
        return error_response("No update fields supplied")

    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id FROM snippets WHERE id = %s", (snippet_id,))
                if not cursor.fetchone():
                    return error_response("Snippet not found", 404)
                if updates:
                    params.append(snippet_id)
                    cursor.execute(f"UPDATE snippets SET {', '.join(updates)} WHERE id = %s", params)
                if "tags" in data:
                    replace_snippet_tags(cursor, snippet_id, data["tags"])
                connection.commit()
                return jsonify({"success": True})
    except Exception as exc:
        return error_response(f"Failed to update snippet: {exc}", 500)


# Deletes a snippet and cascades related snippet_tags rows.
@app.delete("/api/snippets/<int:snippet_id>")
def delete_snippet(snippet_id):
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM snippets WHERE id = %s", (snippet_id,))
                connection.commit()
                if cursor.rowcount == 0:
                    return error_response("Snippet not found", 404)
                return jsonify({"success": True})
    except Exception as exc:
        return error_response(f"Failed to delete snippet: {exc}", 500)


# Returns all tag names in alphabetical order.
@app.get("/api/tags")
def list_tags():
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT name FROM tags ORDER BY name")
                return jsonify([row["name"] for row in cursor.fetchall()])
    except Exception as exc:
        return error_response(f"Failed to fetch tags: {exc}", 500)


# Returns distinct languages used by saved snippets.
@app.get("/api/languages")
def list_languages():
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT DISTINCT language FROM snippets ORDER BY language")
                return jsonify([row["language"] for row in cursor.fetchall()])
    except Exception as exc:
        return error_response(f"Failed to fetch languages: {exc}", 500)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
