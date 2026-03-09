#!/bin/bash

# Environment Validation Script for Checkpoint 14
# This script checks if all prerequisites are met for deployment testing

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
    ((ERRORS++))
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

print_header() {
    echo ""
    echo "========================================="
    echo "$1"
    echo "========================================="
}

# Check 1: Required files exist
print_header "Checking Required Files"

if [ -f "scripts/deploy.sh" ]; then
    print_success "Deployment script exists"
else
    print_error "Deployment script not found: scripts/deploy.sh"
fi

if [ -f "cdk/app.py" ]; then
    print_success "CDK app exists"
else
    print_error "CDK app not found: cdk/app.py"
fi

if [ -f "runtime/strands_agent.py" ]; then
    print_success "Runtime agent exists"
else
    print_error "Runtime agent not found: runtime/strands_agent.py"
fi

if [ -f "cli/sales_agent_cli.py" ]; then
    print_success "CLI tool exists"
else
    print_error "CLI tool not found: cli/sales_agent_cli.py"
fi

if [ -f "buildspec.yml" ]; then
    print_success "BuildSpec exists"
else
    print_error "BuildSpec not found: buildspec.yml"
fi

# Check 2: Script permissions
print_header "Checking Script Permissions"

if [ -x "scripts/deploy.sh" ]; then
    print_success "Deployment script is executable"
else
    print_warning "Deployment script is not executable (run: chmod +x scripts/deploy.sh)"
fi

# Check 3: AWS CLI
print_header "Checking AWS CLI"

if command -v aws &> /dev/null; then
    AWS_VERSION=$(aws --version 2>&1 | cut -d' ' -f1)
    print_success "AWS CLI installed: $AWS_VERSION"
else
    print_error "AWS CLI not installed"
fi

# Check 4: AWS Credentials
print_header "Checking AWS Credentials"

if aws sts get-caller-identity &> /dev/null; then
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    USER_ARN=$(aws sts get-caller-identity --query Arn --output text)
    print_success "AWS credentials configured"
    echo "  Account: $ACCOUNT_ID"
    echo "  User: $USER_ARN"
else
    print_error "AWS credentials not configured or invalid"
    echo "  Run: aws configure"
fi

# Check 5: AWS CDK CLI
print_header "Checking AWS CDK CLI"

if command -v cdk &> /dev/null; then
    CDK_VERSION=$(cdk --version 2>&1)
    print_success "AWS CDK CLI installed: $CDK_VERSION"
    
    # Check version is >= 2.100.0
    CDK_MAJOR=$(echo "$CDK_VERSION" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | cut -d. -f1)
    CDK_MINOR=$(echo "$CDK_VERSION" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | cut -d. -f2)
    
    if [ "$CDK_MAJOR" -ge 2 ] && [ "$CDK_MINOR" -ge 100 ]; then
        print_success "CDK version meets requirements (>= 2.100.0)"
    else
        print_warning "CDK version may be too old (requires >= 2.100.0)"
    fi
else
    print_error "AWS CDK CLI not installed"
    echo "  Run: npm install -g aws-cdk"
fi

# Check 6: Python
print_header "Checking Python"

if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    print_success "Python installed: $PYTHON_VERSION"
    
    # Check version is >= 3.13
    PYTHON_MAJOR=$(python3 --version | grep -oE '[0-9]+\.[0-9]+' | cut -d. -f1)
    PYTHON_MINOR=$(python3 --version | grep -oE '[0-9]+\.[0-9]+' | cut -d. -f2)
    
    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 13 ]; then
        print_success "Python version meets requirements (>= 3.13)"
    else
        print_warning "Python version may be too old (requires >= 3.13)"
    fi
else
    print_error "Python 3 not installed"
fi

# Check 7: Python Dependencies
print_header "Checking Python Dependencies"

if [ -f "requirements.txt" ]; then
    print_success "Root requirements.txt exists"
    
    # Try to check if dependencies are installed
    if python3 -c "import aws_cdk" &> /dev/null; then
        print_success "aws-cdk-lib installed"
    else
        print_warning "aws-cdk-lib not installed (run: pip install -r requirements.txt)"
    fi
else
    print_error "requirements.txt not found"
fi

if [ -f "cli/requirements.txt" ]; then
    print_success "CLI requirements.txt exists"
    
    if python3 -c "import boto3" &> /dev/null; then
        print_success "boto3 installed"
    else
        print_warning "boto3 not installed (run: pip install -r cli/requirements.txt)"
    fi
    
    if python3 -c "import click" &> /dev/null; then
        print_success "click installed"
    else
        print_warning "click not installed (run: pip install -r cli/requirements.txt)"
    fi
else
    print_error "cli/requirements.txt not found"
fi

if [ -f "runtime/requirements.txt" ]; then
    print_success "Runtime requirements.txt exists"
else
    print_error "runtime/requirements.txt not found"
fi

# Check 8: Test Framework
print_header "Checking Test Framework"

if python3 -c "import pytest" &> /dev/null; then
    PYTEST_VERSION=$(python3 -c "import pytest; print(pytest.__version__)")
    print_success "pytest installed: $PYTEST_VERSION"
else
    print_warning "pytest not installed (run: pip install pytest)"
fi

# Check 9: Git
print_header "Checking Git"

if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version)
    print_success "Git installed: $GIT_VERSION"
else
    print_error "Git not installed"
fi

# Check 10: Docker (for local testing)
print_header "Checking Docker (Optional)"

if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    print_success "Docker installed: $DOCKER_VERSION"
else
    print_warning "Docker not installed (optional for local container testing)"
fi

# Summary
print_header "Validation Summary"

echo ""
if [ $ERRORS -eq 0 ]; then
    print_success "All critical checks passed!"
    echo ""
    echo "You are ready to run deployment tests."
    echo "Next steps:"
    echo "  1. Review the test plan: .kiro/specs/agentcore-cdk-infrastructure/checkpoint-14-test-plan.md"
    echo "  2. Run deployment: ./scripts/deploy.sh --stage checkpoint14"
    echo "  3. Follow the test plan to validate all components"
else
    print_error "Found $ERRORS critical issue(s)"
    echo ""
    echo "Please fix the errors above before proceeding with deployment tests."
fi

if [ $WARNINGS -gt 0 ]; then
    print_warning "Found $WARNINGS warning(s)"
    echo ""
    echo "Warnings indicate potential issues but may not block deployment."
fi

echo ""

# Exit with error code if there are errors
exit $ERRORS
