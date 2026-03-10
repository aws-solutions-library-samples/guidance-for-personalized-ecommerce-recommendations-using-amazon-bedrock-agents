"""Sales Agent CLI — interact with your deployed AgentCore agent."""

import click
import boto3
from botocore.exceptions import ClientError

from cli import __version__


class SalesAgentCLI:
    """Manages stack context and AWS client interactions for all CLI commands."""

    def __init__(self, stack_name: str, verbosity: int = 0):
        self.stack_name = stack_name
        self.verbosity = verbosity
        self.stack_outputs: dict[str, str] = {}
        self.session: boto3.Session = boto3.Session()

    def validate_credentials(self) -> dict:
        """Call STS GetCallerIdentity. Raises ClickException on failure."""
        try:
            sts = self.create_client("sts")
            identity = sts.get_caller_identity()
            if self.verbosity >= 1:
                click.echo(
                    f"Authenticated as {identity.get('Arn', 'unknown')}"
                )
            return identity
        except ClientError as exc:
            error_code = exc.response["Error"].get("Code", "Unknown")
            error_msg = exc.response["Error"].get("Message", str(exc))
            raise click.ClickException(
                f"AWS credential validation failed: {error_code} — {error_msg}"
            )

    def validate_stack(self) -> dict[str, str]:
        """Call describe_stacks, cache outputs. Raises ClickException if not found."""
        try:
            cfn = self.create_client("cloudformation")
            response = cfn.describe_stacks(StackName=self.stack_name)
            stacks = response.get("Stacks", [])
            if not stacks:
                raise click.ClickException(
                    f"Stack '{self.stack_name}' not found"
                )
            stack = stacks[0]
            self.stack_outputs = {
                o["OutputKey"]: o["OutputValue"]
                for o in stack.get("Outputs", [])
            }
            if self.verbosity >= 2:
                click.echo(f"Stack outputs: {self.stack_outputs}")
            return self.stack_outputs
        except ClientError as exc:
            error_msg = exc.response["Error"].get("Message", str(exc))
            if "does not exist" in error_msg:
                raise click.ClickException(
                    f"Stack '{self.stack_name}' not found"
                )
            raise click.ClickException(
                f"Failed to describe stack '{self.stack_name}': {error_msg}"
            )

    def get_runtime_arn(self) -> str:
        """Return RuntimeArn from stack outputs, or attempt SDK fallback."""
        arn = self.stack_outputs.get("RuntimeArn")
        if arn:
            return arn

        # Fallback: list runtimes via bedrock-agentcore-control SDK
        if self.verbosity >= 1:
            click.echo(
                "RuntimeArn not in stack outputs, attempting SDK fallback..."
            )
        try:
            ac = self.create_client("bedrock-agentcore-control")
            response = ac.list_agent_runtimes()
            runtimes = response.get("agentRuntimeSummaries", [])
            for rt in runtimes:
                rt_name = rt.get("agentRuntimeName", "")
                if self.stack_name.lower() in rt_name.lower():
                    return rt["agentRuntimeArn"]
            # If no name match, return the first runtime if only one exists
            if len(runtimes) == 1:
                return runtimes[0]["agentRuntimeArn"]
        except (ClientError, Exception) as exc:
            if self.verbosity >= 2:
                click.echo(f"SDK fallback failed: {exc}")

        raise click.ClickException(
            f"Could not resolve Runtime ARN for stack '{self.stack_name}'. "
            "Ensure the stack has a 'RuntimeArn' output or a runtime is deployed."
        )

    def get_ssm_prefix(self) -> str:
        """Derive SSM prefix from stack outputs or default to /{stack_name}/."""
        prefix = self.stack_outputs.get("ParameterStorePrefix")
        if prefix:
            if not prefix.startswith("/"):
                prefix = "/" + prefix
            if not prefix.endswith("/"):
                prefix = prefix + "/"
            return prefix
        return f"/{self.stack_name}/"

    def get_log_group(self) -> str:
        """Derive log group from RuntimeId: /aws/bedrock-agentcore/runtimes/{id}-DEFAULT."""
        runtime_id = self.stack_outputs.get("RuntimeId")
        if runtime_id:
            return f"/aws/bedrock-agentcore/runtimes/{runtime_id}-DEFAULT"

        # Try to extract RuntimeId from RuntimeArn
        arn = self.stack_outputs.get("RuntimeArn", "")
        if arn:
            # ARN format: arn:aws:bedrock-agentcore:region:account:runtime/RUNTIME_ID
            parts = arn.split("/")
            if len(parts) >= 2:
                runtime_id = parts[-1]
                return f"/aws/bedrock-agentcore/runtimes/{runtime_id}-DEFAULT"

        raise click.ClickException(
            "Could not determine log group. "
            "Stack outputs missing 'RuntimeId' and 'RuntimeArn'."
        )

    def create_client(self, service: str) -> boto3.client:
        """Create a boto3 client for the given service."""
        return self.session.client(service)


@click.group()
@click.option(
    "--stack-name",
    envvar="AGENTCORE_STACK_NAME",
    required=False,
    help="CloudFormation stack name (or set AGENTCORE_STACK_NAME env var)",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (-v verbose, -vv debug)",
)
@click.pass_context
def cli(ctx, stack_name, verbose):
    """Sales Agent CLI — interact with your deployed AgentCore agent."""
    ctx.ensure_object(dict)
    ctx.obj["verbosity"] = verbose
    ctx.obj["stack_name"] = stack_name


if __name__ == "__main__":
    cli()
