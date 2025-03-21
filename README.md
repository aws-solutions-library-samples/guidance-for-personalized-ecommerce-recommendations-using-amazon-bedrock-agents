# Guidance for building Sales Agent on Amazon Bedrock

## Table of Contents

1. [Overview](#overview-required)
    - [Cost](#cost)
2. [Prerequisites](#prerequisites-required)
    - [Operating System](#operating-system-required)
3. [Deployment Steps](#deployment-steps-required)
4. [Deployment Validation](#deployment-validation-required)
5. [Running the Guidance](#running-the-guidance-required)
6. [Next Steps](#next-steps-required)
7. [Cleanup](#cleanup-required)

## Overview

The Sales Agent on Bedrock draws inspiration from the Rufus Sales Agent, which enhances the shopping experience on Amazon.com. Leveraging cutting-edge generative AI, this solution is designed to deliver personalized and dynamic interactions that drive product discovery and sales. By integrating Amazon Personalize, the Sales Agent provides tailored product recommendations, while Amazon OpenSearch Service enables rapid and accurate search capabilities across your catalog. Together, these technologies create a seamless and engaging customer journey, boosting conversions and satisfaction. The Sales Agent empowers businesses to harness Amazon’s proven AI expertise, transforming their apps and websites into highly effective sales channels.

The architecture of Sales Agent Rufus on Bedrock is illustrated below:
![alt text](sales-agent/assets/images/architecture.png)


### Cost

Cost Considerations Breakdown
When estimating costs, several key factors need to be considered:
1. Storage Costs
    - Amazon S3: Estimated storage of 10 TB.
    - DynamoDB: Stores 10 GB of product data and 1 GB of user data.
    - OpenSearch Serverless: Contains 10 GB of product data.
    - AWS Personalize: Estimated 1-hour training time to process 10 GB of data.

2. Model Training Costs
    - Assumes one training session per month, with each session taking 8 hours to complete.

3. Embedding Process Costs
    - Calls Titan model to generate embeddings.
    - Each request processes 100K tokens as input.
    - The embedding process consumes:
        - 100 OCU indexes in OpenSearch Serverless.
    - 100 reads and 100 writes in DynamoDB.
    - The embedding operation is performed once per month.
    - Assumes 1 million products, with each input containing 10K tokens.

4. Compute Costs
    - Based on 10,000 requests per day, impacting the following services:
        - Bedrock Agent
        - AWS Lambda
        - OpenSearch Serverless
        - DynamoDB
        - AWS Personalize
        - Bedrock model inference
    - Assumes the agent and model use the Haiku model, with each interaction involving:
        - 15K tokens for input
        - 2K tokens for output
        - 100 reads per request in DynamoDB
    - This cost evaluation is based on the us-east-1 region. Your specific scenario may involve higher request volumes or storage needs, leading to different costs. It's important to adjust assumptions based on actual usage patterns. For detailed cost estimation, refer to the AWS Pricing Calculator which is 4.35k per month plus with bedrock.
    - [Pricing Calculator](https://calculator.aws/#/estimate?id=f2842d89bdbaf9d6ce7e90cdb2a3701ba64bad32)

5. Other costs
    - Haiku estimate 15K input and 2K output which is 1.875 K 
    - ($0.00025 * 15 * 10000 + $0.00125 * 2 * 10000 ) *30 = 1875
    - Total is 6.225K

### Sample Cost Table 

The following table provides a sample cost breakdown for deploying this Guidance with the default parameters in the US East (N. Virginia) Region for one month.

| AWS service  | Dimensions | Cost [USD] |
| ----------- | ------------ | ------------ |
| Amazon OpenSearch Service |  How many Search and Query OCUs? (10), How big is the index data? (10 GB), How many Indexing OCUs? (1)| 1,927.44  |
| Amazon DynamoDB | Table class (Standard), Average item size (all attributes) (1 KB), Data storage size (11 GB) | 127.75 |
| Amazon Simple Storage Service (S3)| S3 Standard storage (10000 GB per month), PUT, COPY, POST, LIST requests to S3 Standard (1000000), GET, SELECT, and all other requests from S3 Standard (1000000) DT Inbound: Not selected (0 TB per month), DT Outbound: Internet (1 TB per month) | 327.56 |
| Amazon Personalize|Average amount of data ingested per month (10 GB per month), Number of Users in dataset (1000000), Number of hours recommender is active per month (720), Number of additional recommendations per hour (420), Number of hours with additional recommendations per month (720), Number of recommender hours with metadata enabled per month (720), Number of additional recommendations with metadata enabled per month (300000)|664.30|
| Amazon Bedrock|Number of Input tokens (13000 million per month)|1,300.00|
| AWS Lambda|Architecture (x86), Amount of ephemeral storage allocated (512 MB), Architecture (x86), Invoke Mode (Buffered), Number of requests (10000 per day)|6.40|

## Prerequisites

Before installing the solution, ensure you have the following:

- [GitHub Account](https://docs.github.com/en/get-started/start-your-journey/creating-an-account-on-github)
- Node.js (version 20.15.1 or later)
- npm (usually comes with Node.js)
- Python 3.9 or higher and pip and virtualenv
- Docker 27.0.3 or higher
- AWS CLI [installed](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) and [configured](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html)
- [AWS CDK v2](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html#getting_started_install) installed

### Operating System

These deployment instructions are optimized to best work on **Ubuntu 22.04 or MAC**.  Deployment in another OS may require additional steps.

### AWS account requirements

An AWS IAM account with the following permissions in *us-east-1* region:
  - Create and manage IAM roles and policies.
  - Create and invoke AWS Lambda functions.
  - Create, Read from, and Write to Amazon S3 buckets.
  - Access and manage Amazon Bedrock agents and models.
  - Create and manage Amazon DynamoDB.
  - Create and manage OpenSearch Serverless Collection.
  - Enable and able to access to Amazon Bedrock foundation models 


### aws cdk bootstrap

 This Guidance uses aws-cdk. If you are using aws-cdk for first time, please perform the below bootstrapping command.
 ```bash
    cdk bootstrap
```

### Supported Regions

The solution only be **VERIFIED** in **us-east-1** region.

## Deployment Steps

1. Clone the repository to your environment, set up a virtual environment and activate it , download related data and install required Python packages using below code:
```bash
git clone GITHUB_URL
cd sales-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. CDK Deploymant

```bash
cdk deploy
```

## Deployment Validation

If deployment is successful, you should see CDK outputs of `SalesAgentStack.BedrockAgentName` and `SalesAgentStack.s3DataBucketName` and CREATE_COMPLETE message in terminal.


## Running the Guidance

1. Follow the [steps in WorkShop Studio](https://catalog.us-east-1.prod.workshops.aws/workshops/dc89cbd1-21ed-4d41-904b-69c95c296378/en-US/import-data) to import vector data to OpenSearch Serverless.

2. Follow the [steps in WorkShop Studio](https://catalog.us-east-1.prod.workshops.aws/workshops/dc89cbd1-21ed-4d41-904b-69c95c296378/en-US/personalize) to prepare the Personalize Recommender.

3. Open the Bedrock Agent and test the following sample questions.

```
I'm user_id: 1: Could you recommend some Christmas gifts? (answer should include item_id)
I'm user_id: 2: Can you help me compare the differences between different styles of sofas? (answer should include item_id)
```


## Next Steps

1. Bedrock Agent
* If a customer wants to add filters to a prompt or modify the chatbot workflow, check the Bedrock Agent and edit the instruction settings.
* To change the model that the Bedrock Agent uses for reasoning, update it in the Bedrock Agent console.
If a customer needs to modify Lambda API parameters, update the OpenAPI Schema and the Lambda function code.
2. Data Ingestion
* To integrate a custom dataset, follow the workshop instructions for data ingestion.
* To modify the embedding algorithm or vector search, update the Python code in the import data folder and rerun the process.
3. Model Customization
* To customize the Personalize model, follow the workshop instructions. If needed, update the Lambda function code to change the ARN and API endpoints for invoking Personalize.
For LLM-related tasks, where summarization and invocation occur in Lambda code, update the prompt or switch to the desired model.


## Cleanup 
Please **empty** the s3 bucket before running following command. You can find the s3 bucket name on the command output of `cdk deploy`. Once done, you can issue following command to clean up the resources.

```bash
cdk destroy
```