"""Token Forums Stack — Lambda + CloudFront + S3.

Pre-requisite: tokenburner-base stack must be deployed.
Imports: tokenburner-api-keys-table-name/arn, tokenburner-feature-registry-table-name/arn
"""

import os
import aws_cdk as cdk
from aws_cdk import (
    aws_lambda as _lambda,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_s3 as s3,
    aws_iam as iam,
    custom_resources as cr,
)
from constructs import Construct

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")


class ForumsStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        api_keys_table_name = cdk.Fn.import_value("tokenburner-api-keys-table-name")
        api_keys_table_arn  = cdk.Fn.import_value("tokenburner-api-keys-table-arn")
        feature_registry_table_name = cdk.Fn.import_value("tokenburner-feature-registry-table-name")
        feature_registry_table_arn  = cdk.Fn.import_value("tokenburner-feature-registry-table-arn")

        cdk.Tags.of(self).add("ManagedBy", "tokenburner")
        cdk.Tags.of(self).add("tokenburner:feature", "forums")

        # ── S3 bucket (threads as JSON) ─────────────────────────────────────
        bucket = s3.Bucket(
            self, "ForumsBucket",
            bucket_name=f"tokenburner-forums-{self.account}",
            versioned=True,
            lifecycle_rules=[s3.LifecycleRule(noncurrent_version_expiration=cdk.Duration.days(90))],
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        # ── Lambda ───────────────────────────────────────────────────────────
        fn = _lambda.Function(
            self, "Handler",
            function_name="tokenburner-forums",
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.ARM_64,
            handler="lambda_handler.handler",
            memory_size=512,
            timeout=cdk.Duration.seconds(30),
            code=_lambda.Code.from_asset(
                path=PROJECT_ROOT,
                bundling=cdk.BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_12.bundling_image,
                    platform="linux/arm64",
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output --quiet && "
                        "cp -r app /asset-output/ && "
                        "cp lambda_handler.py /asset-output/ && "
                        "cp -r static /asset-output/",
                    ],
                ),
            ),
            environment={
                "FORUMS_BUCKET": bucket.bucket_name,
                "API_KEYS_TABLE": api_keys_table_name,
            },
        )

        bucket.grant_read_write(fn)
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["dynamodb:GetItem", "dynamodb:UpdateItem"],
            resources=[api_keys_table_arn],
        ))

        fn_url = fn.add_function_url(auth_type=_lambda.FunctionUrlAuthType.NONE)

        distribution = cloudfront.Distribution(
            self, "CDN",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.FunctionUrlOrigin(fn_url),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
            ),
        )

        forums_url = f"https://{distribution.distribution_domain_name}"

        register = cr.AwsCustomResource(
            self, "RegisterFeature",
            on_create=cr.AwsSdkCall(
                service="DynamoDB", action="putItem",
                physical_resource_id=cr.PhysicalResourceId.of("forums-registry"),
                parameters={
                    "TableName": feature_registry_table_name,
                    "Item": {
                        "name":        {"S": "forums"},
                        "title":       {"S": "Token Forums"},
                        "description": {"S": "Threaded discussion board, S3-backed so context files can read it."},
                        "url":         {"S": forums_url},
                        "docs_url":    {"S": forums_url},
                        "health_url":  {"S": f"{forums_url}/health"},
                        "stack_name":  {"S": cdk.Aws.STACK_NAME},
                    },
                },
            ),
            on_update=cr.AwsSdkCall(
                service="DynamoDB", action="putItem",
                physical_resource_id=cr.PhysicalResourceId.of("forums-registry"),
                parameters={
                    "TableName": feature_registry_table_name,
                    "Item": {
                        "name":        {"S": "forums"},
                        "title":       {"S": "Token Forums"},
                        "description": {"S": "Threaded discussion board, S3-backed so context files can read it."},
                        "url":         {"S": forums_url},
                        "docs_url":    {"S": forums_url},
                        "health_url":  {"S": f"{forums_url}/health"},
                        "stack_name":  {"S": cdk.Aws.STACK_NAME},
                    },
                },
            ),
            on_delete=cr.AwsSdkCall(
                service="DynamoDB", action="deleteItem",
                parameters={
                    "TableName": feature_registry_table_name,
                    "Key": {"name": {"S": "forums"}},
                },
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=["dynamodb:PutItem", "dynamodb:DeleteItem"],
                    resources=[feature_registry_table_arn],
                ),
            ]),
        )
        register.node.add_dependency(distribution)

        cdk.CfnOutput(self, "ForumsUrl", value=forums_url)
        cdk.CfnOutput(self, "ForumsBucketName", value=bucket.bucket_name)
