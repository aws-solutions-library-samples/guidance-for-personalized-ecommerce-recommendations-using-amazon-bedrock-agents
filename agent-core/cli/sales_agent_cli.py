"""Sales Agent CLI — interact with your deployed AgentCore agent."""

import asyncio
import json
import re
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import click
import websockets

import boto3
from botocore.exceptions import ClientError
from bedrock_agentcore.runtime import AgentCoreRuntimeClient

try:
    from . import __version__
    from .streaming import StreamingResponseHandler, format_agent_label
except ImportError:
    import sys
    from pathlib import Path
    _parent = str(Path(__file__).resolve().parent.parent)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from cli import __version__
    from cli.streaming import StreamingResponseHandler, format_agent_label

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


@cli.command()
def version():
    """Display the CLI version."""
    click.echo(f"sales-agent-cli {__version__}")


def _get_cli(ctx):
    """Validate stack and create SalesAgentCLI instance, storing it in ctx.obj."""
    stack_name = ctx.obj.get("stack_name")
    if not stack_name:
        raise click.ClickException(
            "Stack name is required. Use --stack-name or set AGENTCORE_STACK_NAME."
        )
    cli_instance = SalesAgentCLI(stack_name, ctx.obj.get("verbosity", 0))
    cli_instance.validate_credentials()
    cli_instance.validate_stack()
    ctx.obj["cli"] = cli_instance
    return cli_instance


@cli.command()
@click.option("--message", "-m", required=True, help="Message to send to the agent")
@click.option("--session-id", default=None, help="Session ID for multi-turn conversation")
@click.option("--actor-id", default=None, help="Actor ID for the invocation")
@click.pass_context
def invoke(ctx, message, session_id, actor_id):
    """Send a single message to the agent and display the response."""
    cli_instance = _get_cli(ctx)
    verbosity = ctx.obj.get("verbosity", 0)

    runtime_arn = cli_instance.get_runtime_arn()
    if verbosity >= 1:
        click.echo(f"Runtime ARN: {runtime_arn}")

    client = AgentCoreRuntimeClient(
        region=cli_instance.session.region_name,
        session=cli_instance.session,
    )
    url = client.generate_presigned_url(
        runtime_arn=runtime_arn, endpoint_name="DEFAULT"
    )

    payload = {"prompt": message}
    if session_id:
        payload["session_id"] = session_id
    if actor_id:
        payload["actor_id"] = actor_id

    async def _invoke():
        async with websockets.connect(url, open_timeout=120, close_timeout=10) as ws:
            await ws.send(json.dumps(payload))
            handler = StreamingResponseHandler(verbosity=verbosity)
            response_text, metrics = await handler.handle_stream(ws)
            return response_text, metrics

    try:
        response_text, metrics = asyncio.run(_invoke())
        if verbosity >= 1 and metrics.time_to_first_token is not None:
            click.echo(
                f"\nTTFB: {metrics.time_to_first_token:.2f}s | "
                f"Total: {metrics.total_duration:.2f}s"
            )
    except Exception as exc:
        raise click.ClickException(f"Invocation failed: {exc}")


@cli.command()
@click.pass_context
def chat(ctx):
    """Start an interactive chat session with the agent."""
    cli_instance = _get_cli(ctx)
    verbosity = ctx.obj.get("verbosity", 0)

    session_id = str(uuid.uuid4())
    log_dir = Path.home() / ".sales-agent-cli" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    runtime_arn = cli_instance.get_runtime_arn()
    client = AgentCoreRuntimeClient(
        region=cli_instance.session.region_name,
        session=cli_instance.session,
    )

    click.echo(f"Chat session started (ID: {session_id})")
    click.echo("Type /help for available commands.\n")

    while True:
        try:
            message = click.prompt(click.style("You", fg="green"), prompt_suffix=": ")
        except (EOFError, KeyboardInterrupt, click.Abort):
            click.echo("\nGoodbye!")
            break

        stripped = message.strip()
        if not stripped:
            continue

        # Slash commands
        if stripped.lower() in ("/exit", "/quit", "/q"):
            click.echo("Goodbye!")
            break
        elif stripped.lower() == "/clear":
            session_id = str(uuid.uuid4())
            click.echo(f"Session cleared. New session ID: {session_id}")
            continue
        elif stripped.lower() == "/session":
            click.echo(f"Session ID: {session_id}")
            continue
        elif stripped.lower() == "/help":
            click.echo("Available commands:")
            click.echo("  /exit, /quit, /q  - End the chat session")
            click.echo("  /clear            - Start a new session")
            click.echo("  /session          - Show current session ID")
            click.echo("  /help             - Show this help message")
            continue

        # Log user message
        _log_interaction(log_dir, session_id, "user", stripped)

        # Send message
        url = client.generate_presigned_url(
            runtime_arn=runtime_arn, endpoint_name="DEFAULT"
        )
        payload = {"prompt": stripped, "session_id": session_id}

        async def _send():
            async with websockets.connect(url, open_timeout=120, close_timeout=10) as ws:
                await ws.send(json.dumps(payload))
                handler = StreamingResponseHandler(verbosity=verbosity, suppress_echo=True)
                return await handler.handle_stream(ws)

        try:
            response_text, metrics = asyncio.run(_send())
            _log_interaction(log_dir, session_id, "assistant", response_text, metrics)
            label = format_agent_label(metrics.time_to_first_token)
            click.echo(label)
            click.echo(response_text)
            if verbosity >= 1 and metrics.time_to_first_token is not None:
                click.echo(f"TTFB: {metrics.time_to_first_token:.2f}s | Total: {metrics.total_duration:.2f}s")
            click.echo("")  # blank line between exchanges
        except Exception as exc:
            click.echo(f"Error: {exc}", err=True)


def _log_interaction(log_dir, session_id, role, content, metrics=None):
    """Append a JSON line to the session log file."""
    log_file = log_dir / f"{session_id}.jsonl"
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "role": role,
        "content": content,
    }
    if metrics and metrics.time_to_first_token is not None:
        entry["metrics"] = {
            "time_to_first_token": metrics.time_to_first_token,
            "total_duration": metrics.total_duration,
        }
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def parse_time_expression(expr):
    """Parse ISO 8601 or relative time expression to epoch milliseconds."""
    expr = expr.strip()

    # Try relative expression: "30m ago", "1h ago", "2d ago"
    match = re.match(r'^(\d+)\s*(s|m|h|d)\s*ago$', expr, re.IGNORECASE)
    if match:
        amount = int(match.group(1))
        unit = match.group(2).lower()
        multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        delta = timedelta(seconds=amount * multipliers[unit])
        ts = datetime.now(timezone.utc) - delta
        return int(ts.timestamp() * 1000)

    # Try ISO 8601
    try:
        if expr.endswith("Z"):
            expr = expr[:-1] + "+00:00"
        dt = datetime.fromisoformat(expr)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        pass

    raise click.ClickException(
        f"Invalid time expression: '{expr}'. Use ISO 8601 or relative (e.g., '1h ago')"
    )


_SEVERITY_COLORS = {
    "ERROR": "red",
    "WARN": "yellow",
    "WARNING": "yellow",
    "INFO": None,
    "DEBUG": "bright_black",
}


def _detect_severity(message):
    """Detect log severity from message text."""
    upper = message.upper()
    for level in ("ERROR", "WARN", "WARNING", "INFO", "DEBUG"):
        if level in upper:
            return level
    return "INFO"


def _format_log_message(message):
    """Format log message, pretty-printing JSON if present."""
    try:
        parsed = json.loads(message)
        return json.dumps(parsed, indent=2)
    except (json.JSONDecodeError, TypeError):
        return message


@cli.command()
@click.option("--tail", type=int, default=None, help="Number of most recent log lines to display")
@click.option("--start", default=None, help="Start time (ISO 8601 or relative, e.g., '1h ago')")
@click.option("--end", default=None, help="End time (ISO 8601 or relative, e.g., '30m ago')")
@click.pass_context
def logs(ctx, tail, start, end):
    """View CloudWatch logs for the agent runtime."""
    cli_instance = _get_cli(ctx)
    verbosity = ctx.obj.get("verbosity", 0)

    log_group = cli_instance.get_log_group()
    if verbosity >= 1:
        click.echo(f"Log group: {log_group}")

    cw = cli_instance.create_client("logs")

    kwargs = {"logGroupName": log_group, "interleaved": True}
    if start:
        kwargs["startTime"] = parse_time_expression(start)
    if end:
        kwargs["endTime"] = parse_time_expression(end)
    if tail:
        kwargs["limit"] = tail

    try:
        response = cw.filter_log_events(**kwargs)
        events = response.get("events", [])

        if not events:
            click.echo("No log events found.")
            return

        for event in events:
            message = event.get("message", "").strip()
            timestamp = event.get("timestamp", 0)
            dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")

            severity = _detect_severity(message)
            color = _SEVERITY_COLORS.get(severity)
            formatted = _format_log_message(message)

            line = f"[{time_str}] {formatted}"
            if color:
                click.echo(click.style(line, fg=color))
            else:
                click.echo(line)
    except ClientError as exc:
        error_code = exc.response["Error"].get("Code", "")
        if error_code == "ResourceNotFoundException":
            raise click.ClickException("Log group not found. Is the runtime deployed?")
        error_msg = exc.response["Error"].get("Message", str(exc))
        raise click.ClickException(f"Failed to retrieve logs: {error_msg}")


@cli.command()
@click.pass_context
def status(ctx):
    """Display deployment status for the current stack."""
    stack_name = ctx.obj.get("stack_name")
    if not stack_name:
        raise click.ClickException(
            "Stack name is required. Use --stack-name or set AGENTCORE_STACK_NAME."
        )

    verbosity = ctx.obj.get("verbosity", 0)
    cli_instance = SalesAgentCLI(stack_name, verbosity)
    cli_instance.validate_credentials()

    cfn = cli_instance.create_client("cloudformation")

    # Describe stack
    try:
        response = cfn.describe_stacks(StackName=stack_name)
        stacks = response.get("Stacks", [])
        if not stacks:
            click.echo(f"No deployment found for stack '{stack_name}'")
            return
    except ClientError as exc:
        if "does not exist" in str(exc):
            click.echo(f"No deployment found for stack '{stack_name}'")
            return
        raise click.ClickException(f"Failed to describe stack: {exc}")

    stack = stacks[0]
    stack_status = stack.get("StackStatus", "UNKNOWN")

    click.echo(f"Stack: {stack_name}")
    click.echo(f"Status: {stack_status}")
    click.echo("")

    # Display outputs
    outputs = stack.get("Outputs", [])
    if outputs:
        click.echo("Outputs:")
        for o in outputs:
            click.echo(f"  {o['OutputKey']}: {o['OutputValue']}")
        click.echo("")

    # Show recent events if transitional
    if stack_status.endswith("_IN_PROGRESS"):
        click.echo("Recent events:")
        try:
            events_resp = cfn.describe_stack_events(StackName=stack_name)
            events = events_resp.get("StackEvents", [])[:5]
            for evt in events:
                ts = evt.get("Timestamp", "")
                resource = evt.get("LogicalResourceId", "")
                evt_status = evt.get("ResourceStatus", "")
                reason = evt.get("ResourceStatusReason", "")
                line = f"  {ts} {resource} {evt_status}"
                if reason:
                    line += f" — {reason}"
                click.echo(line)
        except ClientError:
            click.echo("  (Could not retrieve events)")
        click.echo("")

    # ECS health (best-effort)
    try:
        ecs = cli_instance.create_client("ecs")
        # Try to find ECS cluster/service from stack outputs
        cluster = None
        service = None
        for o in outputs:
            key = o["OutputKey"].lower()
            if "cluster" in key:
                cluster = o["OutputValue"]
            elif "service" in key:
                service = o["OutputValue"]

        if cluster and service:
            ecs_resp = ecs.describe_services(cluster=cluster, services=[service])
            services = ecs_resp.get("services", [])
            if services:
                svc = services[0]
                click.echo("ECS Service:")
                click.echo(f"  Desired: {svc.get('desiredCount', 0)}")
                click.echo(f"  Running: {svc.get('runningCount', 0)}")
                click.echo(f"  Pending: {svc.get('pendingCount', 0)}")
    except (ClientError, Exception):
        if verbosity >= 2:
            click.echo("  (Could not retrieve ECS health)")


if __name__ == "__main__":
    cli()
