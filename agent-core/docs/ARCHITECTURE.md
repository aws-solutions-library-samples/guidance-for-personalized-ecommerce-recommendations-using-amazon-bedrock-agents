# Architecture Diagrams

This document provides detailed architecture diagrams for the AgentCore CDK Infrastructure project.

## Table of Contents

- [High-Level Architecture](#high-level-architecture)
- [CI/CD Pipeline Flow](#cicd-pipeline-flow)
- [Deployment Flow](#deployment-flow)
- [Network Architecture](#network-architecture)
- [Runtime Component Architecture](#runtime-component-architecture)
- [Data Flow](#data-flow)

## High-Level Architecture

```mermaid
graph TB
    subgraph "Developer Workflow"
        DEV[Developer]
        CLI[CLI Tool]
    end
    
    subgraph "CI/CD Pipeline"
        CC[CodeCommit Repository]
        CP[CodePipeline]
        CB[CodeBuild]
        CD[CodeDeploy]
        ECR[ECR Repository]
    end
    
    subgraph "Runtime Infrastructure"
        VPC[VPC]
        RT[Runtime Container<br/>ARM64/Graviton]
        PS[Parameter Store]
        CW[CloudWatch Logs]
    end
    
    subgraph "Data Services"
        DDB[DynamoDB Tables<br/>item_table, user_table]
        AOSS[OpenSearch Serverless<br/>Vector Search]
        PER[Personalize<br/>Recommendations]
        S3[S3 Bucket<br/>Product Images]
        MEM[AgentCore Memory<br/>30-day retention]
    end
    
    subgraph "AI Services"
        BR[Bedrock Models<br/>Titan Embed, Claude, Nova]
    end
    
    DEV -->|git push| CC
    DEV -->|manage| CLI
    CLI -->|read/write| PS
    CLI -->|invoke| RT
    CLI -->|query| CW
    
    CC -->|trigger| CP
    CP -->|build| CB
    CB -->|push image| ECR
    CB -->|test| RT
    CP -->|deploy| CD
    CD -->|update| RT
    
    RT -->|read config| PS
    RT -->|query| DDB
    RT -->|search| AOSS
    RT -->|recommend| PER
    RT -->|store images| S3
    RT -->|context| MEM
    RT -->|inference| BR
    RT -->|logs| CW
    
    VPC -.contains.- RT
    
    style DEV fill:#e1f5ff
    style CLI fill:#e1f5ff
    style CC fill:#fff4e1
    style CP fill:#fff4e1
    style CB fill:#fff4e1
    style CD fill:#fff4e1
    style ECR fill:#fff4e1
    style VPC fill:#f0f0f0
    style RT fill:#c8e6c9
    style PS fill:#c8e6c9
    style CW fill:#c8e6c9
    style DDB fill:#ffe1e1
    style AOSS fill:#ffe1e1
    style PER fill:#ffe1e1
    style S3 fill:#ffe1e1
    style MEM fill:#ffe1e1
    style BR fill:#e1d5ff
```

### Component Descriptions

**Developer Workflow Layer**:
- **Developer**: Writes code, pushes to repository, manages infrastructure
- **CLI Tool**: Command-line interface for parameter management, invocations, and operations

**CI/CD Pipeline Layer**:
- **CodeCommit**: Git repository for source code version control
- **CodePipeline**: Orchestrates automated build and deployment workflow
- **CodeBuild**: Builds ARM64 Docker images, runs tests
- **CodeDeploy**: Performs blue/green deployments with health checks
- **ECR**: Stores container images with versioning

**Runtime Infrastructure Layer**:
- **VPC**: Network isolation with public/private subnets
- **Runtime Container**: Strands SDK agent with native tools (ARM64/Graviton)
- **Parameter Store**: Centralized configuration management
- **CloudWatch Logs**: Structured logging with 30-day retention

**Data Services Layer**:
- **DynamoDB**: Product catalog and user profile storage
- **OpenSearch Serverless**: Vector similarity search for products
- **Personalize**: Collaborative filtering recommendations
- **S3**: Product image storage
- **AgentCore Memory**: Conversation context with 30-day expiry

**AI Services Layer**:
- **Bedrock Models**: Titan Embed (embeddings), Claude/Nova (inference)

## CI/CD Pipeline Flow

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant CC as CodeCommit
    participant CP as CodePipeline
    participant CB as CodeBuild
    participant ECR as ECR
    participant CD as CodeDeploy
    participant RT as Runtime
    participant CW as CloudWatch
    
    Dev->>CC: git push origin main
    Note over Dev,CC: Code changes committed
    
    CC->>CP: Trigger pipeline
    Note over CP: Source stage
    
    CP->>CB: Start build
    Note over CB: Build stage begins
    
    CB->>CB: Install dependencies (uv)
    CB->>CB: Run unit tests (pytest)
    
    alt Tests Pass
        CB->>CB: Build ARM64 Docker image
        CB->>ECR: Push image with commit tag
        CB->>CP: Build success
        
        CP->>CD: Start deployment
        Note over CD: Deploy stage begins
        
        CD->>RT: Deploy new version (blue)
        Note over RT: New container starts
        
        CD->>RT: Health check (300s grace)
        
        alt Health Check Pass
            CD->>RT: Shift traffic to blue
            Note over RT: Traffic cutover
            
            CD->>RT: Terminate old version (green)
            CD->>CP: Deployment success
            CP->>CW: Log success event
        else Health Check Fail
            CD->>RT: Rollback to green
            CD->>CP: Deployment failed
            CP->>CW: Log failure + alarm
        end
    else Tests Fail
        CB->>CP: Build failed
        CP->>CW: Log failure + alarm
        Note over CP: Pipeline halted
    end
```

### Pipeline Stages

**1. Source Stage**:
- Monitors CodeCommit repository main branch
- Triggers on commit
- Outputs source artifact to S3

**2. Build Stage**:
- Installs dependencies using uv
- Runs unit tests with pytest
- Builds ARM64 Docker image
- Pushes image to ECR with commit hash tag
- Generates imagedefinitions.json artifact

**3. Deploy Stage**:
- Creates new container version (blue)
- Runs health checks (300s grace period)
- Shifts traffic atomically
- Terminates old version (green)
- Rolls back on failure

## Deployment Flow

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant Script as deploy.sh
    participant CDK as CDK CLI
    participant CF as CloudFormation
    participant AWS as AWS Services
    
    Dev->>Script: ./deploy.sh --stage dev
    
    Script->>Script: Parse arguments
    Script->>Script: Validate stage name
    
    Script->>AWS: aws sts get-caller-identity
    alt Credentials Valid
        AWS->>Script: Account info
    else Credentials Invalid
        AWS->>Script: Error
        Script->>Dev: "AWS credentials not configured"
        Note over Script: Exit code 1
    end
    
    Script->>AWS: Check CDK bootstrap
    alt Not Bootstrapped
        Script->>CDK: cdk bootstrap
        CDK->>AWS: Create CDKToolkit stack
    end
    
    Script->>CDK: cdk synth
    CDK->>CDK: Generate CloudFormation templates
    CDK->>Script: Templates ready
    
    Script->>CDK: cdk deploy --context stage=dev
    CDK->>CF: Create/Update stack
    
    CF->>AWS: Provision VPC
    CF->>AWS: Create Parameter Store entries
    CF->>AWS: Create IAM roles
    CF->>AWS: Create AgentCore Memory
    CF->>AWS: Create ECR repository
    CF->>AWS: Create CodeCommit repository
    CF->>AWS: Create CodePipeline
    CF->>AWS: Create runtime resources
    CF->>AWS: Create CloudWatch alarms
    
    AWS->>CF: Resource ARNs
    CF->>CDK: Stack outputs
    CDK->>Script: Deployment complete
    
    Script->>Dev: Display outputs
    Note over Dev: VPC ID, Endpoint, Repository URL
```

### Deployment Steps

1. **Argument Parsing**: Parse --stage, --vpc-id, --destroy flags
2. **Credential Validation**: Verify AWS credentials are configured
3. **Bootstrap Check**: Ensure CDK is bootstrapped in account/region
4. **Synthesis**: Generate CloudFormation templates
5. **Deployment**: Create/update stack resources
6. **Output Display**: Show stack outputs for reference

## Network Architecture

```mermaid
graph TB
    subgraph "AWS Cloud"
        subgraph "VPC: 10.0.0.0/16"
            subgraph "Availability Zone 1"
                PUB1[Public Subnet<br/>10.0.1.0/24]
                PRIV1[Private Subnet<br/>10.0.11.0/24]
                NAT1[NAT Gateway]
            end
            
            subgraph "Availability Zone 2"
                PUB2[Public Subnet<br/>10.0.2.0/24]
                PRIV2[Private Subnet<br/>10.0.12.0/24]
                NAT2[NAT Gateway]
            end
            
            IGW[Internet Gateway]
            
            subgraph "VPC Endpoints"
                VPCE_DDB[DynamoDB Endpoint]
                VPCE_S3[S3 Endpoint]
                VPCE_SSM[SSM Endpoint]
            end
            
            subgraph "Security Groups"
                SG_RT[Runtime SG<br/>Inbound: 8000,8080,9000<br/>Outbound: 443]
            end
            
            RT1[Runtime Container 1]
            RT2[Runtime Container 2]
        end
        
        DDB_EXT[DynamoDB]
        S3_EXT[S3]
        SSM_EXT[Systems Manager]
        AOSS_EXT[OpenSearch Serverless]
        PER_EXT[Personalize]
        BR_EXT[Bedrock]
    end
    
    INTERNET[Internet]
    
    INTERNET <-->|HTTPS| IGW
    IGW <--> PUB1
    IGW <--> PUB2
    
    PUB1 --> NAT1
    PUB2 --> NAT2
    
    NAT1 --> PRIV1
    NAT2 --> PRIV2
    
    PRIV1 --> RT1
    PRIV2 --> RT2
    
    RT1 -.->|via VPC endpoint| VPCE_DDB
    RT2 -.->|via VPC endpoint| VPCE_DDB
    VPCE_DDB -.-> DDB_EXT
    
    RT1 -.->|via VPC endpoint| VPCE_S3
    RT2 -.->|via VPC endpoint| VPCE_S3
    VPCE_S3 -.-> S3_EXT
    
    RT1 -.->|via VPC endpoint| VPCE_SSM
    RT2 -.->|via VPC endpoint| VPCE_SSM
    VPCE_SSM -.-> SSM_EXT
    
    RT1 -->|HTTPS via NAT| AOSS_EXT
    RT2 -->|HTTPS via NAT| AOSS_EXT
    
    RT1 -->|HTTPS via NAT| PER_EXT
    RT2 -->|HTTPS via NAT| PER_EXT
    
    RT1 -->|HTTPS via NAT| BR_EXT
    RT2 -->|HTTPS via NAT| BR_EXT
    
    SG_RT -.applies to.- RT1
    SG_RT -.applies to.- RT2
    
    style PUB1 fill:#e3f2fd
    style PUB2 fill:#e3f2fd
    style PRIV1 fill:#fff3e0
    style PRIV2 fill:#fff3e0
    style RT1 fill:#c8e6c9
    style RT2 fill:#c8e6c9
    style SG_RT fill:#ffccbc
```

### Network Configuration

**VPC CIDR**: 10.0.0.0/16

**Subnets**:
- Public Subnet AZ1: 10.0.1.0/24
- Public Subnet AZ2: 10.0.2.0/24
- Private Subnet AZ1: 10.0.11.0/24
- Private Subnet AZ2: 10.0.12.0/24

**Routing**:
- Public subnets route to Internet Gateway
- Private subnets route to NAT Gateway
- VPC endpoints for DynamoDB, S3, SSM (no NAT charges)

**Security Groups**:
- Runtime SG: Inbound 8000, 8080, 9000 from VPC CIDR
- Runtime SG: Outbound 443 to all (for AWS services)

## Runtime Component Architecture

```mermaid
graph TB
    subgraph "Runtime Container"
        subgraph "Initialization Layer"
            INIT[Module-Level Initialization]
            CLIENTS[AWS Service Clients]
            CONFIG[Configuration Loader]
        end
        
        subgraph "Application Layer"
            ENTRY[agent_invocation<br/>@app.entrypoint]
            AGENT[Strands Agent]
            SESSION[Session Manager]
        end
        
        subgraph "Tools Layer"
            SEARCH[search_product<br/>@tool]
            RECOMMEND[get_recommendation<br/>@tool]
        end
        
        subgraph "Service Integration Layer"
            BEDROCK[Bedrock Client<br/>Embeddings + Inference]
            DYNAMO[DynamoDB Client<br/>Query + GetItem]
            OPENSEARCH[OpenSearch Client<br/>Vector Search]
            PERSONALIZE[Personalize Client<br/>GetRecommendations]
        end
    end
    
    subgraph "External Services"
        PS[Parameter Store]
        DDB[DynamoDB Tables]
        AOSS[OpenSearch Serverless]
        PER[Personalize]
        BR[Bedrock Models]
        MEM[AgentCore Memory]
    end
    
    INIT --> CLIENTS
    INIT --> CONFIG
    CONFIG --> PS
    
    CLIENTS --> BEDROCK
    CLIENTS --> DYNAMO
    CLIENTS --> OPENSEARCH
    CLIENTS --> PERSONALIZE
    
    ENTRY --> AGENT
    AGENT --> SESSION
    SESSION --> MEM
    
    AGENT --> SEARCH
    AGENT --> RECOMMEND
    
    SEARCH --> BEDROCK
    SEARCH --> OPENSEARCH
    SEARCH --> DDB
    
    RECOMMEND --> PERSONALIZE
    RECOMMEND --> DYNAMO
    RECOMMEND --> BEDROCK
    
    BEDROCK --> BR
    DYNAMO --> DDB
    OPENSEARCH --> AOSS
    PERSONALIZE --> PER
    
    style INIT fill:#e1f5ff
    style ENTRY fill:#c8e6c9
    style SEARCH fill:#fff4e1
    style RECOMMEND fill:#fff4e1
    style BEDROCK fill:#ffe1e1
    style DYNAMO fill:#ffe1e1
    style OPENSEARCH fill:#ffe1e1
    style PERSONALIZE fill:#ffe1e1
```

### Component Responsibilities

**Initialization Layer**:
- Module-level AWS client initialization (reused across invocations)
- Configuration loading from Parameter Store
- Environment variable processing

**Application Layer**:
- `agent_invocation`: Entrypoint decorated with @app.entrypoint
- Strands Agent: Orchestrates tool execution and LLM interaction
- Session Manager: Manages AgentCore Memory integration

**Tools Layer**:
- `search_product`: Vector similarity search for products
- `get_recommendation`: Personalized product recommendations

**Service Integration Layer**:
- Bedrock Client: Embeddings (Titan) and inference (Claude/Nova)
- DynamoDB Client: Query and GetItem operations
- OpenSearch Client: Vector search with AWSV4SignerAuth
- Personalize Client: GetRecommendations API

## Data Flow

### Search Product Flow

```mermaid
sequenceDiagram
    participant User
    participant Agent as Strands Agent
    participant Tool as search_product
    participant Bedrock as Bedrock<br/>(Titan Embed)
    participant AOSS as OpenSearch<br/>Serverless
    participant DDB as DynamoDB<br/>(item_table)
    
    User->>Agent: "Find me a blue dress"
    Agent->>Tool: search_product(condition="blue dress")
    
    Tool->>Bedrock: Generate embedding
    Note over Bedrock: Titan Embed Image v1
    Bedrock->>Tool: Embedding vector [1024 dims]
    
    Tool->>AOSS: Vector similarity search
    Note over AOSS: k-NN search with cosine similarity
    AOSS->>Tool: Top 5 matching item_ids
    
    loop For each item_id
        Tool->>DDB: GetItem(item_id)
        DDB->>Tool: Item details (price, style, desc)
    end
    
    Tool->>Agent: JSON array of products
    Agent->>User: "Here are blue dresses..."
```

### Get Recommendation Flow

```mermaid
sequenceDiagram
    participant User
    participant Agent as Strands Agent
    participant Tool as get_recommendation
    participant PER as Personalize
    participant DDB as DynamoDB<br/>(item_table)
    participant Bedrock as Bedrock<br/>(Claude/Nova)
    
    User->>Agent: "Show me recommendations"
    Agent->>Tool: get_recommendation(user_id="user-123", preference="casual")
    
    Tool->>PER: GetRecommendations(user_id)
    Note over PER: Collaborative filtering
    PER->>Tool: Recommended item_ids + scores
    
    loop For each item_id
        Tool->>DDB: GetItem(item_id)
        DDB->>Tool: Item details
    end
    
    Tool->>Bedrock: Summarize recommendations
    Note over Bedrock: Claude or Nova model
    Note over Tool: Prompt: "Summarize these products<br/>for user preference: casual"
    Bedrock->>Tool: Natural language summary
    
    Tool->>Agent: JSON with items + summary
    Agent->>User: "Based on your preferences..."
```

### Memory Integration Flow

```mermaid
sequenceDiagram
    participant User
    participant Agent as Strands Agent
    participant Session as Session Manager
    participant Memory as AgentCore Memory
    
    User->>Agent: "What did I ask about earlier?"
    Note over Agent: session_id, actor_id provided
    
    Agent->>Session: Initialize session
    Session->>Memory: Retrieve context
    Note over Memory: Query /facts/{actorId}<br/>top_k=2, relevance_score=0.6
    Memory->>Session: Previous conversation facts
    
    Session->>Agent: Context loaded
    Agent->>Agent: Process with context
    Agent->>User: "Earlier you asked about blue dresses..."
    
    Agent->>Session: Store new facts
    Session->>Memory: Store facts
    Note over Memory: 30-day expiry policy
    Memory->>Session: Stored successfully
```

## Deployment Patterns

### Multi-Stage Deployment

```mermaid
graph LR
    subgraph "AWS Account"
        subgraph "Dev Stage"
            VPC_DEV[VPC-dev]
            RT_DEV[Runtime-dev]
            PS_DEV[/sales-agent/dev/*]
        end
        
        subgraph "Staging Stage"
            VPC_STG[VPC-staging]
            RT_STG[Runtime-staging]
            PS_STG[/sales-agent/staging/*]
        end
        
        subgraph "Prod Stage"
            VPC_PROD[VPC-prod]
            RT_PROD[Runtime-prod]
            PS_PROD[/sales-agent/prod/*]
        end
        
        subgraph "Shared Services"
            ECR[ECR Repositories<br/>sales-agent-dev<br/>sales-agent-staging<br/>sales-agent-prod]
        end
    end
    
    RT_DEV -.-> ECR
    RT_STG -.-> ECR
    RT_PROD -.-> ECR
    
    style VPC_DEV fill:#e3f2fd
    style VPC_STG fill:#fff3e0
    style VPC_PROD fill:#ffebee
    style RT_DEV fill:#c8e6c9
    style RT_STG fill:#fff9c4
    style RT_PROD fill:#ffccbc
```

### Blue/Green Deployment

```mermaid
graph TB
    subgraph "Before Deployment"
        LB1[Load Balancer]
        GREEN1[Green Version<br/>v1.0.0<br/>100% traffic]
        
        LB1 --> GREEN1
    end
    
    subgraph "During Deployment"
        LB2[Load Balancer]
        GREEN2[Green Version<br/>v1.0.0<br/>100% traffic]
        BLUE2[Blue Version<br/>v1.1.0<br/>Health checks]
        
        LB2 --> GREEN2
        LB2 -.health check.-> BLUE2
    end
    
    subgraph "After Cutover"
        LB3[Load Balancer]
        GREEN3[Green Version<br/>v1.0.0<br/>Terminating]
        BLUE3[Blue Version<br/>v1.1.0<br/>100% traffic]
        
        LB3 --> BLUE3
        LB3 -.-> GREEN3
    end
    
    style GREEN1 fill:#c8e6c9
    style GREEN2 fill:#c8e6c9
    style GREEN3 fill:#ffccbc
    style BLUE2 fill:#e3f2fd
    style BLUE3 fill:#c8e6c9
```

## Security Architecture

```mermaid
graph TB
    subgraph "IAM Roles and Policies"
        RUNTIME_ROLE[Runtime Execution Role]
        PIPELINE_ROLE[CodePipeline Role]
        BUILD_ROLE[CodeBuild Role]
        DEPLOY_ROLE[CodeDeploy Role]
    end
    
    subgraph "Least-Privilege Policies"
        POL_DDB[DynamoDB Policy<br/>Query, GetItem<br/>Specific tables only]
        POL_AOSS[OpenSearch Policy<br/>APIAccessAll<br/>Specific collections only]
        POL_PER[Personalize Policy<br/>GetRecommendations<br/>Specific recommenders only]
        POL_BR[Bedrock Policy<br/>InvokeModel<br/>Specific models only]
        POL_SSM[SSM Policy<br/>GetParameter<br/>/sales-agent/* only]
        POL_MEM[Memory Policy<br/>InvokeAgent, Retrieve<br/>Specific memory only]
    end
    
    subgraph "Network Security"
        SG[Security Groups<br/>Inbound: 8000,8080,9000<br/>Outbound: 443]
        NACL[Network ACLs<br/>Default allow]
        VPCE[VPC Endpoints<br/>Private connectivity]
    end
    
    RUNTIME_ROLE --> POL_DDB
    RUNTIME_ROLE --> POL_AOSS
    RUNTIME_ROLE --> POL_PER
    RUNTIME_ROLE --> POL_BR
    RUNTIME_ROLE --> POL_SSM
    RUNTIME_ROLE --> POL_MEM
    
    style RUNTIME_ROLE fill:#c8e6c9
    style POL_DDB fill:#e3f2fd
    style POL_AOSS fill:#e3f2fd
    style POL_PER fill:#e3f2fd
    style POL_BR fill:#e3f2fd
    style POL_SSM fill:#e3f2fd
    style POL_MEM fill:#e3f2fd
    style SG fill:#ffccbc
```

## Monitoring Architecture

```mermaid
graph TB
    subgraph "Runtime"
        RT[Runtime Container]
        OTEL[OpenTelemetry<br/>Instrumentation]
    end
    
    subgraph "CloudWatch"
        LOGS[CloudWatch Logs<br/>/aws/sales-agent/{stage}]
        METRICS[CloudWatch Metrics<br/>Custom namespace: SalesAgent]
        ALARMS[CloudWatch Alarms<br/>Error rate, Latency]
    end
    
    subgraph "Notifications"
        SNS[SNS Topic]
        EMAIL[Email Subscribers]
        SLACK[Slack Integration]
    end
    
    RT --> OTEL
    OTEL --> LOGS
    OTEL --> METRICS
    
    METRICS --> ALARMS
    ALARMS --> SNS
    SNS --> EMAIL
    SNS --> SLACK
    
    style RT fill:#c8e6c9
    style OTEL fill:#e3f2fd
    style LOGS fill:#fff4e1
    style METRICS fill:#fff4e1
    style ALARMS fill:#ffccbc
```

---

## Diagram Formats

All diagrams in this document use Mermaid syntax for easy rendering in:
- GitHub Markdown
- GitLab Markdown
- Documentation sites (MkDocs, Docusaurus, etc.)
- VS Code with Mermaid extension

To render these diagrams:
1. View in GitHub/GitLab (automatic rendering)
2. Use Mermaid Live Editor: https://mermaid.live
3. Install VS Code Mermaid extension
4. Use documentation generators with Mermaid support
