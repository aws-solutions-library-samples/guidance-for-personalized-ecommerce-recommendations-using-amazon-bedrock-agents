# Dockerfile for AgentCore Runtime - ARM64 (Graviton)
FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.13-slim

# Create non-root user
RUN useradd -m -u 1000 bedrock_agentcore

# Set working directory
WORKDIR /app

# Install uv for faster dependency management
RUN pip install --no-cache-dir uv

# Copy requirements file
COPY requirements.txt .

# Install dependencies using uv
RUN uv pip install --system -r requirements.txt

# Copy application code
COPY strands_agent.py .

# Change ownership to non-root user
RUN chown -R bedrock_agentcore:bedrock_agentcore /app

# Switch to non-root user
USER bedrock_agentcore

# Expose ports for runtime
EXPOSE 8000 8080 9000

# Run the strands agent application with unbuffered output
CMD ["python", "-u", "strands_agent.py"]
