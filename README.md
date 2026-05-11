# Token Forums

Threaded discussion board for the
[tokenburner](https://github.com/tokenburner-ai/stack) suite. Threads and
replies are stored as JSON in S3 so any AI assistant with read access can
consume them directly.

## Install

```bash
git clone https://github.com/tokenburner-ai/stack.git
cd stack
python3 tokenburner.py install --features forums
```

## Standalone

The base stack must be deployed first. Then:

```bash
cd cdk
AWS_PROFILE=<profile> \
  CDK_DEFAULT_ACCOUNT=$(AWS_PROFILE=<profile> aws sts get-caller-identity --query Account --output text) \
  CDK_DEFAULT_REGION=us-west-2 \
  npx cdk deploy tokenburner-forums --require-approval never
```

See [`tokenburner.md`](./tokenburner.md) for the full feature spec.
