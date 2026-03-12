"""Configuration module for AgentCore Sales Agent.

Reads configuration from AWS Systems Manager Parameter Store at startup,
falling back to environment variables for any missing values.
"""

import logging
import os
from dataclasses import dataclass

import boto3

logger = logging.getLogger(__name__)

# Fields that have default values (only for non-critical settings)
_DEFAULTS = {
    "item_table_name": "item_table",
    "user_table_name": "user_table",
    "model_id": "us.anthropic.claude-sonnet-4-20250514-v1:0",
}

# Fields that must be present (no default, no None allowed)
# All values should be set in SSM Parameter Store (single source of truth)
_REQUIRED_FIELDS = ("aoss_collection_id", "aoss_region")

# Mapping from config field name to the corresponding environment variable
_ENV_VAR_MAP = {
    "aoss_collection_id": "AOSS_COLLECTION_ID",
    "aoss_region": "AOSS_REGION",
    "item_table_name": "ITEM_TABLE_NAME",
    "user_table_name": "USER_TABLE_NAME",
    "recommender_arn": "RECOMMENDER_ARN",
    "model_id": "MODEL_ID",
}


@dataclass
class Config:
    """Runtime configuration for the Sales Agent."""

    aoss_collection_id: str
    aoss_region: str
    item_table_name: str
    user_table_name: str
    recommender_arn: str | None
    model_id: str
    parameter_store_prefix: str

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from Parameter Store with env-var fallback.

        1. Read PARAMETER_STORE_PREFIX env var (default: /agentcore/sales-agent/)
        2. Call ssm.get_parameters_by_path(Path=prefix) to fetch all params
        3. Map parameter names to config fields
        4. For any missing parameter, fall back to the corresponding env var
        5. Apply defaults for item_table_name, user_table_name, model_id
        6. If Parameter Store is unreachable, log warning and fall back to env vars
        7. Raise ValueError if required fields are missing from both sources
        """
        prefix = os.environ.get("PARAMETER_STORE_PREFIX", "/agentcore/sales-agent/")

        # Attempt to load from Parameter Store
        ps_values = _fetch_parameter_store(prefix)
        logger.info("Parameter Store values: %s", {k: v[:40] for k, v in ps_values.items()})

        # Resolve each field: Parameter Store → env var → default
        resolved: dict[str, str | None] = {}
        for field, env_var in _ENV_VAR_MAP.items():
            value = ps_values.get(field)
            source = "ssm" if value else None
            # Treat "NONE" placeholder as absent (used by CDK for optional SSM params)
            if value == "NONE":
                value = None
                source = None
            if value is None:
                value = os.environ.get(env_var)
                source = "env" if value else None
            if value is None:
                value = _DEFAULTS.get(field)
                source = "default" if value else None
            resolved[field] = value
            logger.info("Config %s = %s (source: %s)", field, value[:40] if value else None, source)

        # Validate required fields
        missing = [f for f in _REQUIRED_FIELDS if not resolved.get(f)]
        if missing:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing)}. "
                "Set them in Parameter Store or as environment variables."
            )

        return cls(
            aoss_collection_id=resolved["aoss_collection_id"],  # type: ignore[arg-type]
            aoss_region=resolved["aoss_region"],  # type: ignore[arg-type]
            item_table_name=resolved["item_table_name"],  # type: ignore[arg-type]
            user_table_name=resolved["user_table_name"],  # type: ignore[arg-type]
            recommender_arn=resolved.get("recommender_arn"),
            model_id=resolved["model_id"],  # type: ignore[arg-type]
            parameter_store_prefix=prefix,
        )


def _fetch_parameter_store(prefix: str) -> dict[str, str]:
    """Fetch all parameters under *prefix* from SSM Parameter Store.

    Returns a dict mapping field names (e.g. ``aoss_collection_id``) to their
    values.  Returns an empty dict if Parameter Store is unreachable.
    """
    try:
        ssm = boto3.client("ssm")
        params: dict[str, str] = {}
        paginator = ssm.get_paginator("get_parameters_by_path")
        for page in paginator.paginate(Path=prefix, Recursive=True):
            for param in page.get("Parameters", []):
                # Strip the prefix to get the field name
                name = param["Name"]
                if name.startswith(prefix):
                    field_name = name[len(prefix):]
                else:
                    field_name = name.rsplit("/", 1)[-1]
                params[field_name] = param["Value"]
        return params
    except Exception as exc:
        logger.warning(
            "Could not read from Parameter Store (prefix=%s): %s. "
            "Falling back to environment variables.",
            prefix,
            exc,
        )
        return {}
