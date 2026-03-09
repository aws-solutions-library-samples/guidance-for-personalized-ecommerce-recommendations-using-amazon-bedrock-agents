#!/usr/bin/env python3
"""
Sales Agent CLI Tool

Command-line interface for managing AWS AgentCore sales agent runtime.
Provides commands for parameter management, runtime invocation, log retrieval,
and deployment status checking.

Requirements: 5.10, 5.11, 13.6
"""

import sys
import logging
import json
from typing import Optional, Dict, Any
from datetime import datetime

import boto3
import click
from botocore.exceptions import ClientError, NoCredentialsError


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SalesAgentCLI:
    """
    Sales Agent CLI class for managing runtime and parameters.
    
    This class encapsulates AWS client initialization and provides methods
    for validating credentials and stage existence.
    
    Attributes:
        stage: Deployment stage identifier (e.g., dev, staging, prod)
        ssm: AWS Systems Manager client for Parameter Store operations
        sts: AWS STS client for credential validation
        logs: AWS CloudWatch Logs client for log retrieval
    """
    
    def __init__(self, stage: str):
        """
        Initialize CLI with stage parameter.
        
        Args:
            stage: Deployment stage identifier
        """
        self.stage = stage
        self.ssm = None
        self.sts = None
        self.logs = None
        
        # Initialize clients after validation
        self._init_clients()
    
    def _init_clients(self) -> None:
        """Initialize AWS service clients."""
        try:
            self.ssm = boto3.client('ssm')
            self.sts = boto3.client('sts')
            self.logs = boto3.client('logs')
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {e}")
            raise
    
    def validate_credentials(self) -> bool:
        """
        Validate AWS credentials are configured and valid.
        
        Uses STS GetCallerIdentity to verify credentials work.
        
        Returns:
            True if credentials are valid
            
        Raises:
            SystemExit: If credentials are invalid or missing
            
        **Validates: Requirement 5.11**
        """
        try:
            response = self.sts.get_caller_identity()
            logger.info(f"AWS credentials valid for account: {response['Account']}")
            return True
        except NoCredentialsError:
            click.echo(
                click.style("Error: AWS credentials not configured or invalid.", fg='red'),
                err=True
            )
            click.echo(
                "Please configure credentials using 'aws configure' or set environment variables:",
                err=True
            )
            click.echo("  AWS_ACCESS_KEY_ID", err=True)
            click.echo("  AWS_SECRET_ACCESS_KEY", err=True)
            click.echo("  AWS_SESSION_TOKEN (if using temporary credentials)", err=True)
            sys.exit(1)
        except ClientError as e:
            click.echo(
                click.style(f"Error: Failed to validate credentials: {e}", fg='red'),
                err=True
            )
            sys.exit(1)
        except Exception as e:
            click.echo(
                click.style(f"Error: Unexpected error validating credentials: {e}", fg='red'),
                err=True
            )
            sys.exit(1)
    
    def validate_stage(self) -> bool:
        """
        Validate stage exists by checking for Parameter Store entries.
        
        Checks if any parameters exist under the stage prefix path.
        If no parameters are found, the stage is considered non-existent.
        
        Returns:
            True if stage exists
            
        Raises:
            SystemExit: If stage does not exist
            
        **Validates: Requirement 13.6**
        """
        try:
            prefix = f"/sales-agent/{self.stage}/"
            response = self.ssm.get_parameters_by_path(
                Path=prefix,
                MaxResults=1
            )
            
            if not response.get('Parameters'):
                # Stage doesn't exist, try to list available stages
                available_stages = self._list_available_stages()
                
                click.echo(
                    click.style(f"Error: Stage '{self.stage}' not found.", fg='red'),
                    err=True
                )
                
                if available_stages:
                    click.echo(f"Available stages: {', '.join(available_stages)}", err=True)
                else:
                    click.echo("No stages found. Deploy a stack first using deploy.sh", err=True)
                
                sys.exit(1)
            
            logger.info(f"Stage '{self.stage}' validated successfully")
            return True
            
        except ClientError as e:
            click.echo(
                click.style(f"Error: Failed to validate stage: {e}", fg='red'),
                err=True
            )
            sys.exit(1)
        except Exception as e:
            click.echo(
                click.style(f"Error: Unexpected error validating stage: {e}", fg='red'),
                err=True
            )
            sys.exit(1)
    
    def _list_available_stages(self) -> list:
        """
        List all available stages by scanning Parameter Store.
        
        Returns:
            List of stage names found in Parameter Store
        """
        try:
            response = self.ssm.get_parameters_by_path(
                Path="/sales-agent/",
                Recursive=True,
                MaxResults=50
            )
            
            stages = set()
            for param in response.get('Parameters', []):
                # Extract stage from path: /sales-agent/{stage}/{key}
                parts = param['Name'].split('/')
                if len(parts) >= 3:
                    stages.add(parts[2])
            
            return sorted(list(stages))
        except Exception as e:
            logger.warning(f"Failed to list available stages: {e}")
            return []
    
    def _list_parameters(self) -> list:
        """
        List all parameter keys for the current stage.
        
        Returns:
            List of parameter key names (without stage prefix)
        """
        try:
            prefix = f"/sales-agent/{self.stage}/"
            response = self.ssm.get_parameters_by_path(
                Path=prefix,
                Recursive=True,
                MaxResults=50
            )
            
            keys = []
            for param in response.get('Parameters', []):
                # Extract key from path: /sales-agent/{stage}/{key}
                key = param['Name'].replace(prefix, '')
                keys.append(key)
            
            return sorted(keys)
        except Exception as e:
            logger.warning(f"Failed to list parameters: {e}")
            return []


def _get_log_group_name(stage: str) -> Optional[str]:
    """
    Get log group name from CloudFormation stack outputs or use default pattern.
    
    Args:
        stage: Deployment stage identifier
    
    Returns:
        Log group name or None if not found
    """
    try:
        cfn = boto3.client('cloudformation')
        stack_name = f"RuntimeStack-{stage}"
        
        response = cfn.describe_stacks(StackName=stack_name)
        
        if not response.get('Stacks'):
            logger.warning(f"Stack {stack_name} not found")
            return None
        
        stack = response['Stacks'][0]
        outputs = stack.get('Outputs', [])
        
        # Find LogGroupName output
        for output in outputs:
            if output['OutputKey'] == 'LogGroupName':
                log_group = output['OutputValue']
                logger.info(f"Found log group: {log_group}")
                return log_group
        
        # Fallback to default pattern if output not found
        default_log_group = f"/aws/sales-agent/{stage}"
        logger.info(f"Using default log group pattern: {default_log_group}")
        return default_log_group
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ValidationError':
            logger.warning(f"Stack {stack_name} does not exist")
            # Return default pattern
            return f"/aws/sales-agent/{stage}"
        logger.error(f"Failed to get log group name: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting log group name: {e}")
        return None


def _parse_time_range(start: Optional[str], end: Optional[str]) -> tuple:
    """
    Parse start and end time parameters into epoch milliseconds.
    
    Args:
        start: Start time string (ISO format or relative like "1h ago")
        end: End time string (ISO format)
    
    Returns:
        Tuple of (start_time_ms, end_time_ms) or (None, None)
    """
    import re
    from datetime import timedelta
    
    start_time = None
    end_time = None
    
    # Parse end time
    if end:
        try:
            end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            end_time = int(end_dt.timestamp() * 1000)
        except ValueError:
            raise ValueError(f"Invalid end time format: {end}. Use ISO format like '2024-01-01 10:00' or '2024-01-01T10:00:00'")
    
    # Parse start time
    if start:
        # Check for relative time format (e.g., "1h ago", "30m ago", "2d ago")
        relative_pattern = r'^(\d+)([smhd])\s*ago$'
        match = re.match(relative_pattern, start.strip())
        
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            
            # Calculate timedelta
            if unit == 's':
                delta = timedelta(seconds=amount)
            elif unit == 'm':
                delta = timedelta(minutes=amount)
            elif unit == 'h':
                delta = timedelta(hours=amount)
            elif unit == 'd':
                delta = timedelta(days=amount)
            else:
                raise ValueError(f"Invalid time unit: {unit}")
            
            start_dt = datetime.now() - delta
            start_time = int(start_dt.timestamp() * 1000)
        else:
            # Try parsing as ISO format
            try:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                start_time = int(start_dt.timestamp() * 1000)
            except ValueError:
                raise ValueError(f"Invalid start time format: {start}. Use ISO format like '2024-01-01 10:00' or relative like '1h ago'")
    
    return start_time, end_time


def _query_cloudwatch_logs(
    logs_client,
    log_group_name: str,
    start_time: Optional[int],
    end_time: Optional[int],
    tail: Optional[int]
) -> list:
    """
    Query CloudWatch Logs using filter_log_events API.
    
    Args:
        logs_client: Boto3 CloudWatch Logs client
        log_group_name: Log group name
        start_time: Start time in epoch milliseconds (optional)
        end_time: End time in epoch milliseconds (optional)
        tail: Number of most recent lines to retrieve (optional)
    
    Returns:
        List of log events
    """
    try:
        # Build filter_log_events parameters
        params = {
            'logGroupName': log_group_name,
            'limit': tail if tail else 100,  # Default to 100 if no tail specified
        }
        
        # Add time range if specified
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        
        # Query logs
        response = logs_client.filter_log_events(**params)
        
        events = response.get('events', [])
        
        # Handle pagination if needed (for non-tail mode)
        next_token = response.get('nextToken')
        while next_token and not tail:
            response = logs_client.filter_log_events(
                nextToken=next_token,
                **params
            )
            events.extend(response.get('events', []))
            next_token = response.get('nextToken')
            
            # Limit total events to prevent overwhelming output
            if len(events) >= 1000:
                logger.warning("Retrieved 1000 events, stopping pagination")
                break
        
        # Sort by timestamp (most recent last)
        events.sort(key=lambda e: e['timestamp'])
        
        # If tail is specified, return only the last N events
        if tail and len(events) > tail:
            events = events[-tail:]
        
        return events
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        
        if error_code == 'ResourceNotFoundException':
            raise Exception(f"Log group '{log_group_name}' not found")
        elif error_code == 'AccessDeniedException':
            raise Exception("Access denied. Ensure IAM permissions for 'logs:FilterLogEvents'")
        else:
            raise Exception(f"CloudWatch Logs API error: {e}")
    except Exception as e:
        raise Exception(f"Failed to query logs: {e}")


def _format_log_event(event: dict) -> str:
    """
    Format a CloudWatch log event for human readability.
    
    Args:
        event: CloudWatch log event dictionary
    
    Returns:
        Formatted log string with timestamp and message
    """
    # Extract timestamp and convert to readable format
    timestamp_ms = event['timestamp']
    timestamp_dt = datetime.fromtimestamp(timestamp_ms / 1000)
    timestamp_str = timestamp_dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]  # Include milliseconds
    
    # Extract message
    message = event['message'].rstrip('\n')
    
    # Try to parse as JSON for structured logs
    try:
        log_data = json.loads(message)
        
        # Extract common fields
        level = log_data.get('level', log_data.get('levelname', 'INFO'))
        msg = log_data.get('message', log_data.get('msg', message))
        
        # Color code by log level
        if level in ['ERROR', 'CRITICAL']:
            level_colored = click.style(level, fg='red', bold=True)
        elif level == 'WARNING':
            level_colored = click.style(level, fg='yellow')
        elif level == 'DEBUG':
            level_colored = click.style(level, fg='cyan')
        else:
            level_colored = click.style(level, fg='green')
        
        # Format structured log
        formatted = f"[{timestamp_str}] {level_colored}: {msg}"
        
        # Add additional fields if present
        extra_fields = {k: v for k, v in log_data.items() 
                       if k not in ['level', 'levelname', 'message', 'msg', 'timestamp', 'time']}
        
        if extra_fields:
            formatted += f" {json.dumps(extra_fields)}"
        
        return formatted
        
    except (json.JSONDecodeError, TypeError):
        # Not JSON, format as plain text
        # Try to extract log level from message
        level = 'INFO'
        for lvl in ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']:
            if lvl in message:
                level = lvl
                break
        
        # Color code by log level
        if level in ['ERROR', 'CRITICAL']:
            level_colored = click.style(level, fg='red', bold=True)
        elif level == 'WARNING':
            level_colored = click.style(level, fg='yellow')
        elif level == 'DEBUG':
            level_colored = click.style(level, fg='cyan')
        else:
            level_colored = click.style(level, fg='white')
        
        return f"[{timestamp_str}] {level_colored}: {message}"


def _get_runtime_arn(stage: str) -> Optional[str]:
    """
    Get AgentCore Runtime ARN from CloudFormation stack outputs or by listing runtimes.
    
    Args:
        stage: Deployment stage identifier
    
    Returns:
        Runtime ARN or None if not found
    """
    try:
        # First try to get from CloudFormation stack outputs
        cfn = boto3.client('cloudformation')
        stack_name = f"RuntimeStack-{stage}"
        
        try:
            response = cfn.describe_stacks(StackName=stack_name)
            
            if response.get('Stacks'):
                stack = response['Stacks'][0]
                outputs = stack.get('Outputs', [])
                
                # Find RuntimeArn output
                for output in outputs:
                    if output['OutputKey'] == 'RuntimeArn':
                        runtime_arn = output['OutputValue']
                        logger.info(f"Found runtime ARN from stack: {runtime_arn}")
                        return runtime_arn
        except ClientError as e:
            if e.response['Error']['Code'] != 'ValidationError':
                logger.warning(f"Failed to get stack outputs: {e}")
        
        # Fallback: List all AgentCore runtimes and find by name pattern
        logger.info(f"Attempting to find runtime by listing AgentCore runtimes")
        agentcore_control = boto3.client('bedrock-agentcore-control', region_name='us-east-1')
        
        response = agentcore_control.list_agent_runtimes()
        
        # Look for runtime with name matching the stage
        # Common patterns: sales_strands_agent, sales_agent_{stage}, etc.
        for runtime in response.get('agentRuntimes', []):
            runtime_name = runtime.get('agentRuntimeName', '')
            runtime_arn = runtime.get('agentRuntimeArn', '')
            
            # Match patterns: sales_strands_agent, sales_agent_*, etc.
            if 'sales' in runtime_name.lower() and 'agent' in runtime_name.lower():
                logger.info(f"Found matching runtime: {runtime_name} -> {runtime_arn}")
                return runtime_arn
        
        logger.warning(f"No AgentCore runtime found for stage {stage}")
        return None
        
    except ClientError as e:
        logger.error(f"Failed to get runtime ARN: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting runtime ARN: {e}")
        return None


def _invoke_runtime(runtime_arn: str, payload: Dict[str, Any], verbosity: int = 0) -> None:
    """
    Invoke runtime using Bedrock AgentCore API with streaming response.
    
    Args:
        runtime_arn: AgentCore Runtime ARN
        payload: Invocation payload with prompt, actor_id, session_id
        verbosity: Output verbosity level (0=normal, 1=verbose, 2=debug)
    
    Raises:
        Exception: If invocation fails
    """
    try:
        import uuid
        import sys
        from datetime import datetime
        from pathlib import Path
        
        # Add parent directory to path to enable imports when running as script
        script_dir = Path(__file__).parent
        parent_dir = script_dir.parent
        if str(parent_dir) not in sys.path:
            sys.path.insert(0, str(parent_dir))
        
        from cli.streaming import StreamingResponseHandler, PerformanceMetrics
        
        # Create bedrock-agentcore client
        agentcore_client = boto3.client('bedrock-agentcore', region_name='us-east-1')
        
        # Generate session ID if not provided (must be at least 33 characters)
        session_id = payload.get('session_id')
        if not session_id:
            session_id = f"cli-session-{uuid.uuid4()}"
        elif len(session_id) < 33:
            # Pad short session IDs to meet minimum length requirement
            session_id = f"{session_id}-{uuid.uuid4()}"
        
        # Prepare payload for AgentCore API
        api_payload = json.dumps({
            "prompt": payload.get("prompt", ""),
            "actor_id": payload.get("actor_id", "default-user"),
        }).encode()
        
        # Initialize performance metrics
        metrics = PerformanceMetrics()
        
        # Generate log file path with timestamp
        log_dir = Path.home() / ".sales-agent-cli" / "logs"
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_file = str(log_dir / f"chat-{timestamp}.log")
        
        # Mark connection start
        metrics.mark_connection_start()
        
        # Invoke the agent runtime via Bedrock AgentCore API
        invoke_response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            runtimeSessionId=session_id,
            payload=api_payload
        )
        
        # Mark connection established
        metrics.mark_connection_established()
        
        # Get the streaming response body
        streaming_body = invoke_response.get('response')
        
        if not streaming_body:
            raise Exception("No response body received from runtime")
        
        # Create streaming response handler
        handler = StreamingResponseHandler(
            verbosity=verbosity,
            log_file=log_file,
            metrics=metrics
        )
        
        # Process the streaming response
        handler.process_stream(streaming_body)
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        
        if error_code == 'ResourceNotFoundException':
            raise Exception(f"Runtime not found: {runtime_arn}")
        elif error_code == 'AccessDeniedException':
            raise Exception(f"Access denied. Ensure IAM permissions for 'bedrock-agentcore:InvokeAgentRuntime'")
        else:
            raise Exception(f"Bedrock AgentCore API error: {error_msg}")
    except Exception as e:
        raise Exception(f"Invocation failed: {e}")


def _display_event(event: Dict[str, Any]) -> None:
    """
    Display a streaming event from the agent.
    
    Args:
        event: Event dictionary from agent stream
    """
    # Handle different event types from Strands SDK
    event_type = event.get('type', 'unknown')
    
    if event_type == 'text':
        # Text content from agent
        text = event.get('content', '')
        click.echo(text, nl=False)
    
    elif event_type == 'tool_call':
        # Tool invocation
        tool_name = event.get('tool_name', 'unknown')
        click.echo(click.style(f"\n[Calling tool: {tool_name}]", fg='yellow'))
    
    elif event_type == 'tool_result':
        # Tool result
        tool_name = event.get('tool_name', 'unknown')
        click.echo(click.style(f"[Tool {tool_name} completed]", fg='yellow'))
    
    elif event_type == 'error':
        # Error event
        error_msg = event.get('error', 'Unknown error')
        click.echo(click.style(f"\n[Error: {error_msg}]", fg='red'))
    
    elif event_type == 'done':
        # Completion event
        click.echo()
    
    else:
        # Unknown event type - display raw
        logger.debug(f"Unknown event type: {event_type}")


# Click CLI Group
@click.group()
@click.option(
    '--stage',
    required=True,
    help='Deployment stage identifier (e.g., dev, staging, prod). Can also be set via AGENTCORE_STAGE environment variable.',
    envvar='AGENTCORE_STAGE'
)
@click.pass_context
def cli(ctx, stage: str):
    """
    Sales Agent CLI - Manage AWS AgentCore sales agent runtime.
    
    This CLI tool provides commands for managing and interacting with the
    AWS AgentCore sales agent runtime deployed via CDK infrastructure.
    
    \b
    COMMANDS:
      param    Manage Parameter Store values (set, get, list)
      invoke   Send messages to the agent runtime
      chat     Start an interactive chat session
      logs     Retrieve CloudWatch logs
      status   Check deployment status
      version  Display CLI version
    
    \b
    GLOBAL OPTIONS:
      --stage TEXT  Deployment stage identifier (required for all commands)
                    Can be set via AGENTCORE_STAGE environment variable
    
    \b
    EXAMPLES:
      # Set environment variable to avoid repeating --stage
      export AGENTCORE_STAGE=dev
      sales-agent-cli param list
      
      # Or specify stage explicitly
      sales-agent-cli --stage dev param list
      sales-agent-cli --stage prod invoke --message "Find blue dresses"
      sales-agent-cli --stage staging logs --tail 50
    
    \b
    GETTING STARTED:
      1. Deploy the runtime stack:
         ./scripts/deploy.sh --stage dev
      
      2. Set required parameters:
         sales-agent-cli --stage dev param set --key item_table --value my-items
         sales-agent-cli --stage dev param set --key user_table --value my-users
      
      3. Check deployment status:
         sales-agent-cli --stage dev status
      
      4. Invoke the agent:
         sales-agent-cli --stage dev invoke --message "Hello"
    
    \b
    For detailed help on any command, use:
      sales-agent-cli COMMAND --help
    
    \b
    DOCUMENTATION:
      Full documentation: https://github.com/your-org/sales-agent-cli
      Report issues: https://github.com/your-org/sales-agent-cli/issues
    
    **Validates: Requirement 5.10, 14.6**
    """
    # Store context for subcommands
    ctx.ensure_object(dict)
    
    # Skip validation if just showing help
    if ctx.invoked_subcommand is None:
        return
    
    # Initialize CLI instance and store in context
    cli_instance = SalesAgentCLI(stage)
    
    # Validate credentials before any operation
    cli_instance.validate_credentials()
    
    # Validate stage exists
    cli_instance.validate_stage()
    
    # Store CLI instance in context for subcommands
    ctx.obj['cli'] = cli_instance


@cli.command()
@click.pass_context
def version(ctx):
    """
    Display CLI version information.
    
    Shows the current version of the Sales Agent CLI tool and the
    active deployment stage.
    
    \b
    EXAMPLES:
      sales-agent-cli --stage dev version
      
      # With environment variable
      export AGENTCORE_STAGE=prod
      sales-agent-cli version
    """
    click.echo("Sales Agent CLI v1.0.0")
    click.echo(f"Stage: {ctx.obj['cli'].stage}")


# Parameter Store management commands
@cli.group()
@click.pass_context
def param(ctx):
    """
    Parameter Store management commands.
    
    Manage AWS Systems Manager Parameter Store values for the runtime.
    All parameters use hierarchical naming: /sales-agent/{stage}/{key}
    
    \b
    SUBCOMMANDS:
      set   Create or update a parameter value
      get   Retrieve a parameter value
      list  Display all parameters for the stage
    
    \b
    PARAMETER KEYS:
      Common parameter keys used by the runtime:
        item_table         - DynamoDB table name for product items
        user_table         - DynamoDB table name for user profiles
        aoss_endpoint      - OpenSearch Serverless endpoint URL
        recommender_arn    - Amazon Personalize recommender ARN
        s3_bucket          - S3 bucket name for product images
        memory_id          - AgentCore Memory resource ID
    
    \b
    EXAMPLES:
      # List all parameters for a stage
      sales-agent-cli --stage dev param list
      
      # Set a parameter value
      sales-agent-cli --stage dev param set --key item_table --value my-items-table
      
      # Get a specific parameter
      sales-agent-cli --stage dev param get --key aoss_endpoint
    
    **Validates: Requirements 5.1, 5.2, 5.3, 14.6**
    """
    pass


@param.command('set')
@click.option('--key', required=True, help='Parameter key name (e.g., item_table, aoss_endpoint)')
@click.option('--value', required=True, help='Parameter value to store')
@click.pass_context
def param_set(ctx, key: str, value: str):
    """
    Set a Parameter Store value.
    
    Creates or updates a parameter in AWS Systems Manager Parameter Store
    with hierarchical naming: /sales-agent/{stage}/{key}
    
    If the parameter already exists, it will be overwritten with the new value.
    
    \b
    OPTIONS:
      --key TEXT    Parameter key name (required)
                    Common keys: item_table, user_table, aoss_endpoint,
                                recommender_arn, s3_bucket, memory_id
      
      --value TEXT  Parameter value to store (required)
    
    \b
    EXAMPLES:
      # Set DynamoDB table names
      sales-agent-cli --stage dev param set --key item_table --value dev-items-table
      sales-agent-cli --stage dev param set --key user_table --value dev-users-table
      
      # Set OpenSearch endpoint
      sales-agent-cli --stage dev param set --key aoss_endpoint \\
        --value https://abc123.us-east-1.aoss.amazonaws.com
      
      # Set Personalize recommender ARN
      sales-agent-cli --stage prod param set --key recommender_arn \\
        --value arn:aws:personalize:us-east-1:123456789012:recommender/my-recommender
      
      # Set S3 bucket name
      sales-agent-cli --stage dev param set --key s3_bucket --value my-product-images
      
      # Set AgentCore Memory ID
      sales-agent-cli --stage dev param set --key memory_id --value mem-abc123def456
    
    \b
    REQUIRED IAM PERMISSIONS:
      - ssm:PutParameter
    
    **Validates: Requirement 5.1, 13.7, 14.6**
    """
    cli_instance = ctx.obj['cli']
    
    try:
        # Construct full parameter path
        param_path = f"/sales-agent/{cli_instance.stage}/{key}"
        
        # Set parameter value
        cli_instance.ssm.put_parameter(
            Name=param_path,
            Value=value,
            Type='String',
            Overwrite=True,
            Description=f"Parameter for {cli_instance.stage} stage"
        )
        
        click.echo(click.style(f"✓ Parameter set successfully:", fg='green'))
        click.echo(f"  Path: {param_path}")
        click.echo(f"  Value: {value}")
        
        logger.info(f"Set parameter {param_path} = {value}")
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        
        if error_code == 'AccessDeniedException':
            click.echo(
                click.style(f"Error: Access denied to Parameter Store.", fg='red'),
                err=True
            )
            click.echo(
                "Ensure your IAM user/role has 'ssm:PutParameter' permission.",
                err=True
            )
        else:
            click.echo(
                click.style(f"Error: Failed to set parameter: {error_msg}", fg='red'),
                err=True
            )
        
        logger.error(f"Failed to set parameter {key}: {e}")
        sys.exit(1)
        
    except Exception as e:
        click.echo(
            click.style(f"Error: Unexpected error: {e}", fg='red'),
            err=True
        )
        logger.error(f"Unexpected error setting parameter {key}: {e}")
        sys.exit(1)


@param.command('get')
@click.option('--key', required=True, help='Parameter key name to retrieve')
@click.pass_context
def param_get(ctx, key: str):
    """
    Get a Parameter Store value.
    
    Retrieves a parameter value from AWS Systems Manager Parameter Store
    using hierarchical naming: /sales-agent/{stage}/{key}
    
    Displays the parameter value along with metadata including type,
    last modified date, and full parameter path.
    
    \b
    OPTIONS:
      --key TEXT  Parameter key name to retrieve (required)
    
    \b
    EXAMPLES:
      # Get DynamoDB table name
      sales-agent-cli --stage dev param get --key item_table
      
      # Get OpenSearch endpoint
      sales-agent-cli --stage prod param get --key aoss_endpoint
      
      # Get Personalize recommender ARN
      sales-agent-cli --stage staging param get --key recommender_arn
      
      # Get AgentCore Memory ID
      sales-agent-cli --stage dev param get --key memory_id
    
    \b
    OUTPUT FORMAT:
      Parameter: <key>
        Path: /sales-agent/{stage}/{key}
        Value: <value>
        Type: String | SecureString
        Last Modified: <timestamp>
    
    \b
    ERROR HANDLING:
      If the parameter is not found, the command will:
      - Display an error message
      - List available parameters for the stage (if any exist)
      - Exit with status code 1
    
    \b
    REQUIRED IAM PERMISSIONS:
      - ssm:GetParameter
    
    **Validates: Requirement 5.2, 13.7, 14.6**
    """
    cli_instance = ctx.obj['cli']
    
    try:
        # Construct full parameter path
        param_path = f"/sales-agent/{cli_instance.stage}/{key}"
        
        # Get parameter value
        response = cli_instance.ssm.get_parameter(
            Name=param_path,
            WithDecryption=True
        )
        
        param = response['Parameter']
        
        click.echo(click.style(f"Parameter: {key}", fg='green'))
        click.echo(f"  Path: {param['Name']}")
        click.echo(f"  Value: {param['Value']}")
        click.echo(f"  Type: {param['Type']}")
        click.echo(f"  Last Modified: {param['LastModifiedDate']}")
        
        logger.info(f"Retrieved parameter {param_path}")
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        
        if error_code == 'ParameterNotFound':
            click.echo(
                click.style(f"Error: Parameter '{key}' not found for stage '{cli_instance.stage}'.", fg='red'),
                err=True
            )
            
            # Suggest available parameters
            try:
                available = cli_instance._list_parameters()
                if available:
                    click.echo(f"\nAvailable parameters for stage '{cli_instance.stage}':", err=True)
                    for param_key in available:
                        click.echo(f"  - {param_key}", err=True)
            except Exception:
                pass
                
        elif error_code == 'AccessDeniedException':
            click.echo(
                click.style(f"Error: Access denied to Parameter Store.", fg='red'),
                err=True
            )
            click.echo(
                "Ensure your IAM user/role has 'ssm:GetParameter' permission.",
                err=True
            )
        else:
            click.echo(
                click.style(f"Error: Failed to get parameter: {error_msg}", fg='red'),
                err=True
            )
        
        logger.error(f"Failed to get parameter {key}: {e}")
        sys.exit(1)
        
    except Exception as e:
        click.echo(
            click.style(f"Error: Unexpected error: {e}", fg='red'),
            err=True
        )
        logger.error(f"Unexpected error getting parameter {key}: {e}")
        sys.exit(1)


@param.command('list')
@click.pass_context
def param_list(ctx):
    """
    List all Parameter Store values for the stage.
    
    Displays all parameters under the stage prefix: /sales-agent/{stage}/
    Shows parameter keys, values (truncated if long), and types in a
    formatted table.
    
    \b
    EXAMPLES:
      # List all parameters for development stage
      sales-agent-cli --stage dev param list
      
      # List parameters for production
      sales-agent-cli --stage prod param list
      
      # Use with environment variable
      export AGENTCORE_STAGE=staging
      sales-agent-cli param list
    
    \b
    OUTPUT FORMAT:
      Parameters for stage '{stage}':
      
        <key>  <value>  (<type>)
        ...
      
      Total: N parameter(s)
    
    \b
    NOTES:
      - Long values (>60 characters) are truncated with "..."
      - Parameters are sorted alphabetically by key name
      - If no parameters exist, guidance is provided for adding them
    
    \b
    REQUIRED IAM PERMISSIONS:
      - ssm:GetParametersByPath
    
    **Validates: Requirement 5.3, 13.7, 14.6**
    """
    cli_instance = ctx.obj['cli']
    
    try:
        # Get all parameters for stage
        prefix = f"/sales-agent/{cli_instance.stage}/"
        
        response = cli_instance.ssm.get_parameters_by_path(
            Path=prefix,
            Recursive=True,
            WithDecryption=True,
            MaxResults=50
        )
        
        parameters = response.get('Parameters', [])
        
        if not parameters:
            click.echo(
                click.style(f"No parameters found for stage '{cli_instance.stage}'.", fg='yellow')
            )
            click.echo("\nTo add parameters, use:")
            click.echo(f"  sales-agent-cli --stage {cli_instance.stage} param set --key KEY --value VALUE")
            return
        
        click.echo(click.style(f"Parameters for stage '{cli_instance.stage}':", fg='green', bold=True))
        click.echo()
        
        # Sort parameters by key name
        parameters.sort(key=lambda p: p['Name'])
        
        # Display in table format
        max_key_len = max(len(p['Name'].split('/')[-1]) for p in parameters)
        
        for param in parameters:
            key = param['Name'].split('/')[-1]
            value = param['Value']
            param_type = param['Type']
            
            # Truncate long values
            if len(value) > 60:
                value = value[:57] + "..."
            
            click.echo(f"  {key:<{max_key_len}}  {value}  ({param_type})")
        
        click.echo()
        click.echo(f"Total: {len(parameters)} parameter(s)")
        
        logger.info(f"Listed {len(parameters)} parameters for stage {cli_instance.stage}")
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        
        if error_code == 'AccessDeniedException':
            click.echo(
                click.style(f"Error: Access denied to Parameter Store.", fg='red'),
                err=True
            )
            click.echo(
                "Ensure your IAM user/role has 'ssm:GetParametersByPath' permission.",
                err=True
            )
        else:
            click.echo(
                click.style(f"Error: Failed to list parameters: {error_msg}", fg='red'),
                err=True
            )
        
        logger.error(f"Failed to list parameters: {e}")
        sys.exit(1)
        
    except Exception as e:
        click.echo(
            click.style(f"Error: Unexpected error: {e}", fg='red'),
            err=True
        )
        logger.error(f"Unexpected error listing parameters: {e}")
        sys.exit(1)


@cli.command()
@click.option('--message', required=True, help='Chat message to send to the agent')
@click.option('--session-id', help='Session ID for conversation continuity (optional, auto-generated if not provided)')
@click.option('--actor-id', help='Actor/user ID for personalization (optional, defaults to "default-user")')
@click.pass_context
def invoke(ctx, message: str, session_id: Optional[str] = None, actor_id: Optional[str] = None):
    """
    Invoke the runtime with a chat message.
    
    Sends a message to the AgentCore runtime and streams the response in real-time.
    The runtime processes the message using the Strands SDK agent with native tools
    for product search and recommendations.
    
    \b
    OPTIONS:
      --message TEXT      Chat message to send to the agent (required)
                          Natural language query about products or recommendations
      
      --session-id TEXT   Session ID for conversation continuity (optional)
                          Use the same session ID to maintain conversation context
                          Auto-generated if not provided
      
      --actor-id TEXT     Actor/user ID for personalization (optional)
                          Used for personalized recommendations
                          Defaults to "default-user" if not provided
    
    \b
    EXAMPLES:
      # Simple product search
      sales-agent-cli --stage dev invoke --message "Find me a blue dress"
      
      # Search with specific requirements
      sales-agent-cli --stage dev invoke \\
        --message "I need a formal dress under $100"
      
      # Get personalized recommendations
      sales-agent-cli --stage dev invoke \\
        --message "Show me recommendations" \\
        --actor-id user-12345
      
      # Continue a conversation (use same session-id)
      sales-agent-cli --stage dev invoke \\
        --message "What about in red?" \\
        --session-id s-20240101120000
      
      # Multi-turn conversation with personalization
      sales-agent-cli --stage prod invoke \\
        --message "I'm looking for summer dresses" \\
        --actor-id user-789 \\
        --session-id my-shopping-session
    
    \b
    RESPONSE FORMAT:
      The agent streams responses in real-time, showing:
      - Text responses from the agent
      - Tool calls (e.g., [Calling tool: search_product])
      - Tool results (e.g., [Tool search_product completed])
      - Errors (if any occur)
    
    \b
    AGENT CAPABILITIES:
      The agent can:
      - Search products by description, style, color, price
      - Provide personalized recommendations based on user history
      - Answer questions about products
      - Help with product comparisons
      - Maintain conversation context across multiple turns
    
    \b
    TROUBLESHOOTING:
      If invocation fails:
      1. Check deployment status: sales-agent-cli --stage dev status
      2. View recent logs: sales-agent-cli --stage dev logs --tail 50
      3. Verify runtime endpoint exists in CloudFormation outputs
      4. Check VPC and security group allow inbound traffic
      5. Verify ALB target health
    
    \b
    REQUIRED IAM PERMISSIONS:
      - cloudformation:DescribeStacks (to get runtime endpoint)
    
    **Validates: Requirements 5.4, 5.5, 5.6, 13.7, 14.6**
    """
    cli_instance = ctx.obj['cli']
    
    try:
        # Get runtime ARN from CloudFormation stack outputs or by listing runtimes
        runtime_arn = _get_runtime_arn(cli_instance.stage)
        
        if not runtime_arn:
            click.echo(
                click.style("Error: Runtime ARN not found.", fg='red'),
                err=True
            )
            click.echo("\nTroubleshooting steps:", err=True)
            click.echo("  1. Verify the runtime is deployed:", err=True)
            click.echo(f"     aws cloudformation describe-stacks --stack-name RuntimeStack-{cli_instance.stage}", err=True)
            click.echo("  2. Check if the runtime is registered with Bedrock AgentCore:", err=True)
            click.echo(f"     aws bedrock-agentcore-control list-agent-runtimes", err=True)
            sys.exit(1)
        
        # Build invocation payload
        payload = {
            "prompt": message,
        }
        
        if actor_id:
            payload["actor_id"] = actor_id
        
        if session_id:
            payload["session_id"] = session_id
        
        # Display invocation info
        click.echo(click.style("Invoking runtime...", fg='cyan'))
        click.echo(f"  Runtime ARN: {runtime_arn}")
        click.echo(f"  Message: {message}")
        if actor_id:
            click.echo(f"  Actor ID: {actor_id}")
        if session_id:
            click.echo(f"  Session ID: {session_id}")
        click.echo()
        
        # Display response header
        click.echo(click.style("Agent Response:", fg='green', bold=True))
        
        # Invoke runtime via Bedrock AgentCore API and stream response
        _invoke_runtime(runtime_arn, payload)
        
        logger.info(f"Successfully invoked runtime for stage {cli_instance.stage}")
        
    except KeyboardInterrupt:
        click.echo("\n\nInvocation interrupted by user.", err=True)
        sys.exit(130)
        
    except Exception as e:
        click.echo(
            click.style(f"\nError: Failed to invoke runtime: {e}", fg='red'),
            err=True
        )
        click.echo("\nTroubleshooting steps:", err=True)
        click.echo(f"  1. Verify the runtime is deployed:", err=True)
        click.echo(f"     sales-agent-cli --stage {cli_instance.stage} status", err=True)
        click.echo(f"  2. Check CloudWatch logs:", err=True)
        click.echo(f"     sales-agent-cli --stage {cli_instance.stage} logs --tail 50", err=True)
        click.echo(f"  3. Verify IAM permissions for 'bedrock-agentcore:InvokeAgentRuntime'", err=True)
        click.echo(f"  4. Check if the runtime is registered:", err=True)
        click.echo(f"     aws bedrock-agentcore-control list-agent-runtimes", err=True)
        
        logger.error(f"Failed to invoke runtime: {e}")
        sys.exit(1)


@cli.command()
@click.option('--actor-id', help='Actor/user ID for personalization (optional, defaults to "default-user")')
@click.option('-v', '--verbose', count=True, help='Increase output verbosity (use -v for verbose, -vv for debug)')
@click.pass_context
def chat(ctx, actor_id: Optional[str] = None, verbose: int = 0):
    """
    Start an interactive chat session with the agent.
    
    Opens an interactive REPL (Read-Eval-Print Loop) for multi-turn conversations
    with the AgentCore runtime. Maintains conversation context across multiple
    messages within the same session.
    
    \b
    OPTIONS:
      --actor-id TEXT  Actor/user ID for personalization (optional)
                       Used for personalized recommendations
                       Defaults to "default-user" if not provided
      -v, --verbose    Increase output verbosity
                       -v: Show thinking content and performance metrics
                       -vv: Show all raw streaming events and detailed timing
    
    \b
    FEATURES:
      - Multi-turn conversations with context preservation
      - Real-time streaming responses
      - Session ID automatically generated and maintained
      - Command history (use up/down arrows)
      - Automatic logging to ~/.sales-agent-cli/logs/
      - Performance metrics tracking (connection time, TTFB, total time)
      - Special commands:
        /exit, /quit, /q  - Exit the chat session
        /clear            - Clear the screen
        /session          - Display current session ID
        /help             - Show available commands
    
    \b
    EXAMPLES:
      # Start a basic chat session
      sales-agent-cli --stage dev chat
      
      # Start chat with personalization
      sales-agent-cli --stage dev chat --actor-id user-12345
      
      # Chat session example:
      You: Find me a blue dress
      Agent: [streams response with product recommendations]
      
      You: What about in red?
      Agent: [continues conversation with context]
      
      You: /exit
      Goodbye!
    
    \b
    CHAT COMMANDS:
      /exit, /quit, /q  Exit the chat session
      /clear            Clear the terminal screen
      /session          Show the current session ID
      /help             Display help information
    
    \b
    USAGE TIPS:
      - The agent remembers previous messages in the conversation
      - Use natural language to ask questions or make requests
      - Press Ctrl+C to interrupt a response
      - Press Ctrl+D or type /exit to end the session
      - Session context is maintained until you exit
    
    \b
    TROUBLESHOOTING:
      If chat fails to start:
      1. Check deployment status: sales-agent-cli --stage dev status
      2. Verify runtime is accessible: sales-agent-cli --stage dev invoke --message "test"
      3. Check CloudWatch logs: sales-agent-cli --stage dev logs --tail 50
    
    \b
    REQUIRED IAM PERMISSIONS:
      - bedrock-agentcore:InvokeAgentRuntime
      - cloudformation:DescribeStacks (to get runtime ARN)
    
    **Interactive chat mode for conversational AI interactions**
    """
    cli_instance = ctx.obj['cli']
    
    try:
        import uuid
        import os
        
        # Get runtime ARN
        runtime_arn = _get_runtime_arn(cli_instance.stage)
        
        if not runtime_arn:
            click.echo(
                click.style("Error: Runtime ARN not found.", fg='red'),
                err=True
            )
            click.echo("\nTroubleshooting steps:", err=True)
            click.echo("  1. Verify the runtime is deployed:", err=True)
            click.echo(f"     aws cloudformation describe-stacks --stack-name RuntimeStack-{cli_instance.stage}", err=True)
            click.echo("  2. Check if the runtime is registered with Bedrock AgentCore:", err=True)
            click.echo(f"     aws bedrock-agentcore-control list-agent-runtimes", err=True)
            sys.exit(1)
        
        # Generate session ID for this chat session
        session_id = f"chat-session-{uuid.uuid4()}"
        
        # Set actor ID
        if not actor_id:
            actor_id = "default-user"
        
        # Display welcome message
        click.echo(click.style("=" * 70, fg='cyan'))
        click.echo(click.style("  Sales Agent Interactive Chat", fg='cyan', bold=True))
        click.echo(click.style("=" * 70, fg='cyan'))
        click.echo()
        click.echo(f"  Stage: {click.style(cli_instance.stage, fg='green')}")
        click.echo(f"  Actor ID: {click.style(actor_id, fg='green')}")
        click.echo(f"  Session ID: {click.style(session_id[:20] + '...', fg='green')}")
        click.echo()
        click.echo(click.style("  Type your message and press Enter to chat.", fg='white'))
        click.echo(click.style("  Commands: /exit, /quit, /q (exit) | /clear (clear screen) | /session (show session) | /help", fg='yellow'))
        click.echo(click.style("=" * 70, fg='cyan'))
        click.echo()
        
        # Chat loop
        message_count = 0
        
        while True:
            try:
                # Get user input
                user_input = click.prompt(
                    click.style("You", fg='blue', bold=True),
                    type=str,
                    prompt_suffix=click.style(": ", fg='blue')
                )
                
                # Handle empty input
                if not user_input.strip():
                    continue
                
                # Handle special commands
                command = user_input.strip().lower()
                
                if command in ['/exit', '/quit', '/q']:
                    click.echo()
                    click.echo(click.style("Goodbye! Chat session ended.", fg='green'))
                    click.echo(f"Total messages: {message_count}")
                    break
                
                elif command == '/clear':
                    # Clear screen
                    os.system('clear' if os.name != 'nt' else 'cls')
                    click.echo(click.style("Screen cleared.", fg='green'))
                    continue
                
                elif command == '/session':
                    click.echo()
                    click.echo(click.style(f"Current Session ID: {session_id}", fg='green'))
                    click.echo()
                    continue
                
                elif command == '/help':
                    click.echo()
                    click.echo(click.style("Available Commands:", fg='cyan', bold=True))
                    click.echo("  /exit, /quit, /q  - Exit the chat session")
                    click.echo("  /clear            - Clear the terminal screen")
                    click.echo("  /session          - Display current session ID")
                    click.echo("  /help             - Show this help message")
                    click.echo()
                    continue
                
                # Build invocation payload
                payload = {
                    "prompt": user_input,
                    "actor_id": actor_id,
                    "session_id": session_id,
                }
                
                # Invoke runtime and stream response (thinking indicator shown inside)
                click.echo()
                _invoke_runtime(runtime_arn, payload, verbosity=verbose)
                
                click.echo()
                
                message_count += 1
                
            except KeyboardInterrupt:
                # Handle Ctrl+C gracefully
                click.echo()
                click.echo()
                click.echo(click.style("Response interrupted. Continue chatting or type /exit to quit.", fg='yellow'))
                click.echo()
                continue
            
            except EOFError:
                # Handle Ctrl+D
                click.echo()
                click.echo()
                click.echo(click.style("Goodbye! Chat session ended.", fg='green'))
                click.echo(f"Total messages: {message_count}")
                break
        
        logger.info(f"Chat session ended for stage {cli_instance.stage}, {message_count} messages exchanged")
        
    except KeyboardInterrupt:
        click.echo()
        click.echo()
        click.echo(click.style("Chat session interrupted by user.", fg='yellow'))
        sys.exit(130)
        
    except Exception as e:
        click.echo()
        click.echo(
            click.style(f"Error: Failed to start chat session: {e}", fg='red'),
            err=True
        )
        click.echo("\nTroubleshooting steps:", err=True)
        click.echo(f"  1. Verify the runtime is deployed:", err=True)
        click.echo(f"     sales-agent-cli --stage {cli_instance.stage} status", err=True)
        click.echo(f"  2. Check CloudWatch logs:", err=True)
        click.echo(f"     sales-agent-cli --stage {cli_instance.stage} logs --tail 50", err=True)
        click.echo(f"  3. Verify IAM permissions for 'bedrock-agentcore:InvokeAgentRuntime'", err=True)
        
        logger.error(f"Failed to start chat session: {e}")
        sys.exit(1)


@cli.command()
@click.option('--tail', type=int, help='Number of most recent log lines to retrieve (e.g., 50, 100)')
@click.option('--start', help='Start time for log retrieval (ISO format "2024-01-01 10:00" or relative "1h ago")')
@click.option('--end', help='End time for log retrieval (ISO format "2024-01-01 11:00")')
@click.pass_context
def logs(ctx, tail: Optional[int] = None, start: Optional[str] = None, end: Optional[str] = None):
    """
    Retrieve runtime logs from CloudWatch.
    
    Queries CloudWatch Logs for the runtime log group and displays logs
    in human-readable format with timestamps and color-coded log levels.
    Supports tail mode for recent logs and time range filtering.
    
    \b
    OPTIONS:
      --tail INTEGER  Number of most recent log lines to retrieve
                      Useful for quick checks of recent activity
                      Example: --tail 50
      
      --start TEXT    Start time for log retrieval
                      Formats:
                        - ISO: "2024-01-01 10:00" or "2024-01-01T10:00:00"
                        - Relative: "1h ago", "30m ago", "2d ago"
                      Units: s (seconds), m (minutes), h (hours), d (days)
      
      --end TEXT      End time for log retrieval (ISO format)
                      Example: "2024-01-01 11:00"
    
    \b
    EXAMPLES:
      # Get last 100 log lines
      sales-agent-cli --stage dev logs --tail 100
      
      # Get logs from the last hour
      sales-agent-cli --stage dev logs --start "1h ago"
      
      # Get logs from the last 30 minutes
      sales-agent-cli --stage prod logs --start "30m ago"
      
      # Get logs for a specific time range
      sales-agent-cli --stage dev logs \\
        --start "2024-01-01 10:00" \\
        --end "2024-01-01 11:00"
      
      # Get logs from 2 days ago
      sales-agent-cli --stage staging logs --start "2d ago"
      
      # Quick check of recent errors
      sales-agent-cli --stage prod logs --tail 50
    
    \b
    OUTPUT FORMAT:
      Logs are displayed with:
      - Timestamp (YYYY-MM-DD HH:MM:SS.mmm)
      - Color-coded log level (ERROR=red, WARNING=yellow, INFO=green, DEBUG=cyan)
      - Log message
      - Additional structured fields (if present)
    
    \b
    LOG LEVELS:
      ERROR/CRITICAL  - Red, bold (critical issues requiring attention)
      WARNING         - Yellow (potential issues)
      INFO            - Green (normal operations)
      DEBUG           - Cyan (detailed debugging information)
    
    \b
    NOTES:
      - If no options are provided, retrieves last 100 log lines
      - Logs are sorted chronologically (oldest first)
      - Structured JSON logs are parsed and formatted for readability
      - Maximum 1000 events retrieved to prevent overwhelming output
    
    \b
    TROUBLESHOOTING:
      If log retrieval fails:
      1. Verify log group exists:
         aws logs describe-log-groups --log-group-name-prefix /aws/sales-agent/{stage}
      2. Check IAM permissions for 'logs:FilterLogEvents'
      3. Ensure runtime has generated logs by invoking it:
         sales-agent-cli --stage dev invoke --message "test"
    
    \b
    REQUIRED IAM PERMISSIONS:
      - logs:FilterLogEvents
      - cloudformation:DescribeStacks (to get log group name)
    
    **Validates: Requirements 5.7, 5.8, 10.8, 14.6**
    """
    cli_instance = ctx.obj['cli']
    
    try:
        # Get log group name from CloudFormation stack outputs or use default pattern
        log_group_name = _get_log_group_name(cli_instance.stage)
        
        if not log_group_name:
            click.echo(
                click.style("Error: Log group not found.", fg='red'),
                err=True
            )
            click.echo(f"\nExpected log group: /aws/sales-agent/{cli_instance.stage}", err=True)
            click.echo("\nTroubleshooting steps:", err=True)
            click.echo("  1. Verify the runtime is deployed:", err=True)
            click.echo(f"     aws cloudformation describe-stacks --stack-name SalesAgentRuntimeStack-{cli_instance.stage}", err=True)
            click.echo("  2. Check if log group exists:", err=True)
            click.echo(f"     aws logs describe-log-groups --log-group-name-prefix /aws/sales-agent/{cli_instance.stage}", err=True)
            sys.exit(1)
        
        # Parse time parameters
        start_time, end_time = _parse_time_range(start, end)
        
        # Query CloudWatch Logs
        events = _query_cloudwatch_logs(
            cli_instance.logs,
            log_group_name,
            start_time,
            end_time,
            tail
        )
        
        if not events:
            click.echo(click.style("No log events found for the specified criteria.", fg='yellow'))
            return
        
        # Display logs in human-readable format
        click.echo(click.style(f"Logs from {log_group_name}:", fg='green', bold=True))
        click.echo()
        
        for event in events:
            formatted_log = _format_log_event(event)
            click.echo(formatted_log)
        
        click.echo()
        click.echo(click.style(f"✓ Retrieved {len(events)} log event(s)", fg='green'))
        
        logger.info(f"Retrieved {len(events)} log events for stage {cli_instance.stage}")
        
    except KeyboardInterrupt:
        click.echo("\n\nLog retrieval interrupted by user.", err=True)
        sys.exit(130)
        
    except Exception as e:
        click.echo(
            click.style(f"Error: Failed to retrieve logs: {e}", fg='red'),
            err=True
        )
        click.echo("\nTroubleshooting steps:", err=True)
        click.echo(f"  1. Verify the log group exists:", err=True)
        click.echo(f"     aws logs describe-log-groups --log-group-name-prefix /aws/sales-agent/{cli_instance.stage}", err=True)
        click.echo(f"  2. Check IAM permissions for 'logs:FilterLogEvents'", err=True)
        click.echo(f"  3. Verify the runtime has generated logs:", err=True)
        click.echo(f"     sales-agent-cli --stage {cli_instance.stage} invoke --message 'test'", err=True)
        
        logger.error(f"Failed to retrieve logs: {e}")
        sys.exit(1)


@cli.command()
@click.pass_context
def status(ctx):
    """
    Display runtime deployment status.
    
    Queries CloudFormation stack status and displays comprehensive information
    about the runtime deployment including stack status, outputs, ECS service
    health, and recent CloudFormation events.
    
    \b
    DISPLAYED INFORMATION:
      Stack Information:
        - Stack name and current status
        - Creation and last update timestamps
        - Status reason (if applicable)
      
      Stack Outputs:
        - RuntimeEndpoint: URL for invoking the agent
        - LogGroupName: CloudWatch log group name
        - ECRRepositoryUri: Container image repository
        - VpcId: VPC identifier
        - Other deployment-specific outputs
      
      ECS Service Status (if applicable):
        - Cluster and service names
        - Health status (HEALTHY/DEGRADED/UNHEALTHY)
        - Desired, running, and pending task counts
        - Task definition version
      
      Recent Events (if deployment in progress):
        - Last 10 CloudFormation events
        - Resource status changes
        - Failure reasons (if any)
    
    \b
    EXAMPLES:
      # Check development environment status
      sales-agent-cli --stage dev status
      
      # Check production deployment
      sales-agent-cli --stage prod status
      
      # Monitor deployment progress
      watch -n 5 'sales-agent-cli --stage dev status'
    
    \b
    STATUS INDICATORS:
      ✓ (Green)   - Deployment complete and operational
      ⟳ (Yellow)  - Deployment in progress
      ✗ (Red)     - Deployment failed or rolled back
    
    \b
    STACK STATUSES:
      CREATE_COMPLETE      - Stack created successfully
      UPDATE_COMPLETE      - Stack updated successfully
      CREATE_IN_PROGRESS   - Stack creation in progress
      UPDATE_IN_PROGRESS   - Stack update in progress
      ROLLBACK_COMPLETE    - Stack creation failed and rolled back
      UPDATE_ROLLBACK_*    - Stack update failed and rolled back
      DELETE_COMPLETE      - Stack deleted successfully
    
    \b
    ECS HEALTH STATUSES:
      HEALTHY    - All desired tasks are running
      DEGRADED   - Some tasks running, but not all desired tasks
      UNHEALTHY  - No tasks running
    
    \b
    USE CASES:
      - Verify deployment completed successfully
      - Check runtime health before invoking
      - Monitor deployment progress
      - Troubleshoot deployment failures
      - Get runtime endpoint for manual testing
      - Verify resource configuration
    
    \b
    TROUBLESHOOTING:
      If stack not found:
      1. Verify the stage name is correct
      2. Check if stack was deployed:
         aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE
      3. Deploy the stack:
         ./scripts/deploy.sh --stage {stage}
      
      If deployment failed:
      1. View detailed CloudFormation events:
         aws cloudformation describe-stack-events --stack-name SalesAgentRuntimeStack-{stage}
      2. Check CloudFormation console for error details
      3. Review IAM permissions and resource quotas
    
    \b
    REQUIRED IAM PERMISSIONS:
      - cloudformation:DescribeStacks
      - cloudformation:DescribeStackResources
      - cloudformation:DescribeStackEvents
      - ecs:DescribeServices (for ECS service status)
    
    **Validates: Requirement 5.9, 14.6**
    """
    cli_instance = ctx.obj['cli']
    
    try:
        cfn = boto3.client('cloudformation')
        ecs = boto3.client('ecs')
        stack_name = f"RuntimeStack-{cli_instance.stage}"
        
        # Get stack information
        try:
            response = cfn.describe_stacks(StackName=stack_name)
            
            if not response.get('Stacks'):
                click.echo(
                    click.style(f"Error: Stack '{stack_name}' not found.", fg='red'),
                    err=True
                )
                click.echo("\nThe runtime has not been deployed for this stage.", err=True)
                click.echo(f"\nTo deploy, run:", err=True)
                click.echo(f"  ./scripts/deploy_bootstrap.sh --stage {cli_instance.stage} --item-table <table> --user-table <table> --aoss-endpoint <endpoint> --personalize-arn <arn>", err=True)
                sys.exit(1)
            
            stack = response['Stacks'][0]
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ValidationError':
                click.echo(
                    click.style(f"Error: Stack '{stack_name}' not found.", fg='red'),
                    err=True
                )
                click.echo("\nThe runtime has not been deployed for this stage.", err=True)
                click.echo(f"\nTo deploy, run:", err=True)
                click.echo(f"  ./scripts/deploy_bootstrap.sh --stage {cli_instance.stage} --item-table <table> --user-table <table> --aoss-endpoint <endpoint> --personalize-arn <arn>", err=True)
                sys.exit(1)
            raise
        
        # Display stack status
        click.echo(click.style(f"Deployment Status for Stage: {cli_instance.stage}", fg='cyan', bold=True))
        click.echo("=" * 70)
        click.echo()
        
        # Stack information
        stack_status = stack['StackStatus']
        creation_time = stack['CreationTime']
        last_updated = stack.get('LastUpdatedTime', creation_time)
        
        # Color code status
        if 'COMPLETE' in stack_status:
            status_colored = click.style(stack_status, fg='green', bold=True)
        elif 'IN_PROGRESS' in stack_status:
            status_colored = click.style(stack_status, fg='yellow', bold=True)
        elif 'FAILED' in stack_status or 'ROLLBACK' in stack_status:
            status_colored = click.style(stack_status, fg='red', bold=True)
        else:
            status_colored = click.style(stack_status, fg='white')
        
        click.echo(click.style("Stack Information:", fg='cyan', bold=True))
        click.echo(f"  Stack Name:        {stack['StackName']}")
        click.echo(f"  Status:            {status_colored}")
        click.echo(f"  Created:           {creation_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        click.echo(f"  Last Updated:      {last_updated.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        if stack.get('StackStatusReason'):
            click.echo(f"  Status Reason:     {stack['StackStatusReason']}")
        
        click.echo()
        
        # Stack outputs
        outputs = stack.get('Outputs', [])
        if outputs:
            click.echo(click.style("Stack Outputs:", fg='cyan', bold=True))
            
            # Find key outputs
            runtime_endpoint = None
            log_group_name = None
            ecr_repository = None
            vpc_id = None
            
            for output in outputs:
                key = output['OutputKey']
                value = output['OutputValue']
                description = output.get('Description', '')
                
                # Store key values for later use
                if key == 'RuntimeEndpoint':
                    runtime_endpoint = value
                elif key == 'LogGroupName':
                    log_group_name = value
                elif key == 'ECRRepositoryUri':
                    ecr_repository = value
                elif key == 'VpcId':
                    vpc_id = value
                
                # Display output
                click.echo(f"  {key}:")
                click.echo(f"    {value}")
                if description:
                    click.echo(f"    ({description})")
            
            click.echo()
        else:
            click.echo(click.style("No stack outputs available.", fg='yellow'))
            click.echo()
        
        # ECS service status (if runtime is deployed on ECS)
        try:
            # Try to find ECS cluster and service from stack resources
            resources_response = cfn.describe_stack_resources(StackName=stack_name)
            resources = resources_response.get('StackResources', [])
            
            cluster_name = None
            service_name = None
            
            for resource in resources:
                if resource['ResourceType'] == 'AWS::ECS::Cluster':
                    cluster_name = resource['PhysicalResourceId']
                elif resource['ResourceType'] == 'AWS::ECS::Service':
                    service_arn = resource['PhysicalResourceId']
                    service_name = service_arn.split('/')[-1]
            
            if cluster_name and service_name:
                click.echo(click.style("ECS Service Status:", fg='cyan', bold=True))
                
                # Get service details
                service_response = ecs.describe_services(
                    cluster=cluster_name,
                    services=[service_name]
                )
                
                if service_response.get('services'):
                    service = service_response['services'][0]
                    
                    desired_count = service['desiredCount']
                    running_count = service['runningCount']
                    pending_count = service['pendingCount']
                    
                    # Health status
                    if running_count == desired_count and desired_count > 0:
                        health = click.style("HEALTHY", fg='green', bold=True)
                    elif running_count > 0:
                        health = click.style("DEGRADED", fg='yellow', bold=True)
                    else:
                        health = click.style("UNHEALTHY", fg='red', bold=True)
                    
                    click.echo(f"  Cluster:           {cluster_name}")
                    click.echo(f"  Service:           {service_name}")
                    click.echo(f"  Health:            {health}")
                    click.echo(f"  Desired Tasks:     {desired_count}")
                    click.echo(f"  Running Tasks:     {running_count}")
                    click.echo(f"  Pending Tasks:     {pending_count}")
                    
                    # Get task definition version
                    task_def = service.get('taskDefinition', '')
                    if task_def:
                        task_def_name = task_def.split('/')[-1]
                        click.echo(f"  Task Definition:   {task_def_name}")
                    
                    click.echo()
                else:
                    click.echo(f"  Service '{service_name}' not found in cluster '{cluster_name}'")
                    click.echo()
        
        except Exception as e:
            # ECS service info is optional, don't fail if not available
            logger.debug(f"Could not retrieve ECS service status: {e}")
        
        # Show recent CloudFormation events if stack is in progress
        if 'IN_PROGRESS' in stack_status:
            click.echo(click.style("Recent CloudFormation Events:", fg='cyan', bold=True))
            
            events_response = cfn.describe_stack_events(StackName=stack_name)
            events = events_response.get('StackEvents', [])
            
            # Show last 10 events
            recent_events = events[:10]
            
            for event in recent_events:
                timestamp = event['Timestamp'].strftime('%H:%M:%S')
                resource_type = event.get('ResourceType', 'N/A')
                logical_id = event.get('LogicalResourceId', 'N/A')
                status = event['ResourceStatus']
                reason = event.get('ResourceStatusReason', '')
                
                # Color code event status
                if 'COMPLETE' in status:
                    status_colored = click.style(status, fg='green')
                elif 'IN_PROGRESS' in status:
                    status_colored = click.style(status, fg='yellow')
                elif 'FAILED' in status:
                    status_colored = click.style(status, fg='red')
                else:
                    status_colored = status
                
                click.echo(f"  [{timestamp}] {logical_id} ({resource_type})")
                click.echo(f"    Status: {status_colored}")
                if reason:
                    click.echo(f"    Reason: {reason}")
            
            click.echo()
        
        # Summary
        click.echo("=" * 70)
        
        if 'COMPLETE' in stack_status:
            click.echo(click.style("✓ Runtime is deployed and operational", fg='green', bold=True))
        elif 'IN_PROGRESS' in stack_status:
            click.echo(click.style("⟳ Deployment in progress...", fg='yellow', bold=True))
        elif 'FAILED' in stack_status or 'ROLLBACK' in stack_status:
            click.echo(click.style("✗ Deployment failed or rolled back", fg='red', bold=True))
            click.echo("\nTo view detailed error information:", err=True)
            click.echo(f"  aws cloudformation describe-stack-events --stack-name {stack_name}", err=True)
        
        logger.info(f"Retrieved status for stage {cli_instance.stage}")
        
    except KeyboardInterrupt:
        click.echo("\n\nStatus check interrupted by user.", err=True)
        sys.exit(130)
        
    except Exception as e:
        click.echo(
            click.style(f"Error: Failed to retrieve deployment status: {e}", fg='red'),
            err=True
        )
        click.echo("\nTroubleshooting steps:", err=True)
        click.echo(f"  1. Verify the stack exists:", err=True)
        click.echo(f"     aws cloudformation describe-stacks --stack-name RuntimeStack-{cli_instance.stage}", err=True)
        click.echo(f"  2. Check IAM permissions for 'cloudformation:DescribeStacks'", err=True)
        click.echo(f"  3. Verify you're in the correct AWS region", err=True)
        
        logger.error(f"Failed to retrieve status: {e}")
        sys.exit(1)


def main():
    """Main entry point for CLI."""
    try:
        cli(obj={})
    except Exception as e:
        logger.error(f"CLI error: {e}")
        click.echo(click.style(f"Error: {e}", fg='red'), err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
