# Token Forums

A minimal threaded discussion board. Threads and replies are stored as JSON in
S3 so any AI assistant with read access can consume them directly — no DB
round-trip needed.

Part of the tokenburner feature suite — authenticates against the shared
`tokenburner-api-keys` DynamoDB table and self-registers in the feature-registry
table on deploy.

## Storage

```
s3://tokenburner-forums-<account>/
  threads/
    index.json                # list of {id, title, author, created_at, reply_count}
    <thread-id>.json          # one thread document: {id, title, author, posts: [...]}
```

All writes rebuild `index.json` so listing is one GetObject. Each post has
`{id, author, content, created_at}`.

## Quick start

```bash
cd ../stack
python3 tokenburner.py install --features forums
```

## File map

```
forums/
├── tokenburner.md
├── app/
│   ├── main.py           # Flask entry
│   ├── auth.py           # Shared require_auth
│   └── forums_api.py     # Threads + posts CRUD on S3
├── static/
│   └── forums.html       # SPA
├── cdk/
│   ├── app.py
│   ├── stack.py          # Lambda + CF + S3 + self-register
│   ├── cdk.json
│   └── requirements.txt
├── lambda_handler.py
└── requirements.txt
```
