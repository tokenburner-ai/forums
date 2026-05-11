"""Forums API — S3-backed threads and posts.

Storage layout (bucket = FORUMS_BUCKET):
  threads/index.json            — list view {threads: [{id, title, author, created_at, reply_count}]}
  threads/<id>.json             — one thread {id, title, author, created_at, posts: [{id, author, content, created_at}]}
"""

import json
import os
import re
import time
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from flask import Blueprint, jsonify, request

from auth import require_auth

forums_bp = Blueprint("forums_bp", __name__)

FORUMS_BUCKET = os.environ.get("FORUMS_BUCKET", "")
INDEX_KEY = "threads/index.json"
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")

_s3 = None


def _client():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3", region_name=AWS_REGION)
    return _s3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:48] or uuid.uuid4().hex[:8]


def _get_json(key: str, default):
    try:
        resp = _client().get_object(Bucket=FORUMS_BUCKET, Key=key)
        return json.loads(resp["Body"].read())
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return default
        raise


def _put_json(key: str, body) -> None:
    _client().put_object(
        Bucket=FORUMS_BUCKET, Key=key,
        Body=json.dumps(body, separators=(",", ":")).encode(),
        ContentType="application/json",
    )


def _load_index() -> list:
    return _get_json(INDEX_KEY, {"threads": []}).get("threads", [])


def _save_index(threads: list) -> None:
    _put_json(INDEX_KEY, {"threads": threads})


@forums_bp.route("/api/forums/threads")
@require_auth
def list_threads():
    threads = _load_index()
    threads.sort(key=lambda t: t.get("last_activity", t.get("created_at", "")), reverse=True)
    return jsonify({"threads": threads})


@forums_bp.route("/api/forums/threads", methods=["POST"])
@require_auth
def create_thread():
    body = request.get_json() or {}
    title = (body.get("title") or "").strip()
    content = (body.get("content") or "").strip()
    if not title or not content:
        return jsonify({"error": "title and content required"}), 400

    author = request.identity.name
    ts = _now()
    index = _load_index()
    existing_ids = {t["id"] for t in index}
    base = _slugify(title)
    tid = base
    n = 2
    while tid in existing_ids:
        tid = f"{base}-{n}"
        n += 1

    thread_doc = {
        "id": tid,
        "title": title,
        "author": author,
        "created_at": ts,
        "posts": [{
            "id": uuid.uuid4().hex[:12],
            "author": author,
            "content": content,
            "created_at": ts,
        }],
    }
    _put_json(f"threads/{tid}.json", thread_doc)
    index.insert(0, {
        "id": tid, "title": title, "author": author,
        "created_at": ts, "last_activity": ts, "reply_count": 0,
    })
    _save_index(index)
    return jsonify(thread_doc), 201


@forums_bp.route("/api/forums/threads/<tid>")
@require_auth
def get_thread(tid):
    doc = _get_json(f"threads/{tid}.json", None)
    if not doc:
        return jsonify({"error": "not found"}), 404
    return jsonify(doc)


@forums_bp.route("/api/forums/threads/<tid>/posts", methods=["POST"])
@require_auth
def reply(tid):
    body = request.get_json() or {}
    content = (body.get("content") or "").strip()
    if not content:
        return jsonify({"error": "content required"}), 400

    doc = _get_json(f"threads/{tid}.json", None)
    if not doc:
        return jsonify({"error": "thread not found"}), 404

    ts = _now()
    post = {
        "id": uuid.uuid4().hex[:12],
        "author": request.identity.name,
        "content": content,
        "created_at": ts,
    }
    doc.setdefault("posts", []).append(post)
    _put_json(f"threads/{tid}.json", doc)

    index = _load_index()
    for t in index:
        if t["id"] == tid:
            t["last_activity"] = ts
            t["reply_count"] = len(doc["posts"]) - 1
            break
    _save_index(index)
    return jsonify(post), 201
