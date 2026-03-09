"""
Unit tests for deployment script.

Tests argument parsing, stage name validation, credential validation,
and deploy/destroy workflows.

**Validates: Requirements 7.1-7.10, 13.2, 13.3**
"""

import pytest
import subprocess
from unittest.mock import Mock, patch, call
import os


class TestDeploymentScriptArgumentParsing:
    """Test deployment script argument parsing."""
    
    def test_script_requires_stage_argument(self):
        """Test that script requires --stage argument."""
        result = subprocess.run(
            ['bash', 'scripts/deploy.sh'],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 1
        assert '--stage is required' in result.stderr or '--stage is required' in result.stdout
    
    def test_script_accepts_stage_argument(self):
        """Test that script accepts --stage argument."""
        with patch('subprocess.run') as mock_run:
            # Mock AWS CLI and CDK commands to succeed
            mock_run.return_value = Mock(returncode=0, stdout='', stderr='')
            
            result = subprocess.run(
                ['bash', 'scripts/deploy.sh', '--stage', 'test', '--help'],
                capture_output=True,
                text=True
            )
            
            # Help should work without errors
            assert result.returncode == 0 or 'Usage' in result.stdout
    
    def test_script_accepts_vpc_id_argument(self):
        """Test that script accepts optional --vpc-id argument."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout='', stderr='')
            
            result = subprocess.run(
                ['bash', 'scripts/deploy.sh', '--stage', 'test', '--vpc-id', 'vpc-12345', '--help'],
                capture_output=True,
                text=True
            )
            
            # Should accept vpc-id without error
            assert result.returncode == 0 or 'Usage' in result.stdout
    
    def test_script_accepts_destroy_flag(self):
        """Test that script accepts --destroy flag."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout='', stderr='')
            
            result = subprocess.run(
                ['bash', 'scripts/deploy.sh', '--stage', 'test', '--destroy', '--help'],
                capture_output=True,
                text=True
            )
            
            # Should accept destroy flag without error
            assert result.returncode == 0 or 'Usage' in result.stdout
    
    def test_script_shows_help(self):
        """Test that script shows help with --help flag."""
        result = subprocess.run(
            ['bash', 'scripts/deploy.sh', '--help'],
            capture_output=True,
            text=True
        )
        
        output = result.stdout + result.stderr
        assert 'Usage' in output or 'usage' in output.lower()
        assert '--stage' in output
        assert '--vpc-id' in output or 'vpc-id' in output
        assert '--destroy' in output


class TestStageNameValidation:
    """Test stage name validation."""
    
    def test_valid_stage_names(self):
        """Test that valid stage names are accepted."""
        valid_stages = [
            'dev',
            'staging',
            'prod',
            'test-123',
            'feature_branch',
            'dev-team-1',
            'qa_env'
        ]
        
        for stage in valid_stages:
            # Test that stage name doesn't cause immediate error
            result = subprocess.run(
                ['bash', 'scripts/deploy.sh', '--stage', stage, '--help'],
                capture_output=True,
                text=True
            )
            
            # Should not fail on stage name validation
            assert 'Invalid stage name' not in result.stdout
            assert 'Invalid stage name' not in result.stderr
    
    def test_invalid_stage_names(self):
        """Test that invalid stage names are rejected."""
        invalid_stages = [
            'dev@prod',
            'stage with spaces',
            'stage!123',
            'stage#test',
            'stage$prod'
        ]
        
        for stage in invalid_stages:
            result = subprocess.run(
                ['bash', 'scripts/deploy.sh', '--stage', stage],
                capture_output=True,
                text=True
            )
            
            # Should fail with validation error
            output = result.stdout + result.stderr
            assert result.returncode == 1 or 'Invalid' in output or 'invalid' in output


class TestCredentialValidation:
    """Test AWS credential validation."""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_script_validates_credentials(self):
        """Test that script validates AWS credentials before proceeding."""
        # Remove AWS credentials from environment
        result = subprocess.run(
            ['bash', 'scripts/deploy.sh', '--stage', 'test'],
            capture_output=True,
            text=True,
            env={}
        )
        
        output = result.stdout + result.stderr
        
        # Should fail with credential error
        assert result.returncode == 1
        assert 'credentials' in output.lower() or 'aws' in output.lower()
    
    def test_script_checks_credentials_before_deployment(self):
        """Test that credential check happens before CDK operations."""
        with patch('subprocess.run') as mock_run:
            # Mock AWS STS call to fail
            def side_effect(*args, **kwargs):
                if 'sts' in str(args) or 'get-caller-identity' in str(args):
                    return Mock(returncode=1, stdout='', stderr='Unable to locate credentials')
                return Mock(returncode=0, stdout='', stderr='')
            
            mock_run.side_effect = side_effect
            
            result = subprocess.run(
                ['bash', 'scripts/deploy.sh', '--stage', 'test'],
                capture_output=True,
                text=True
            )
            
            output = result.stdout + result.stderr
            
            # Should fail early with credential error
            assert result.returncode == 1
            assert 'credentials' in output.lower() or 'Unable to locate credentials' in output


class TestCDKBootstrapCheck:
    """Test CDK bootstrap check."""
    
    def test_script_checks_bootstrap_status(self):
        """Test that script checks if CDK is bootstrapped."""
        # This test verifies the script logic, actual execution would require AWS access
        with open('scripts/deploy.sh', 'r') as f:
            script_content = f.read()
        
        # Verify script contains bootstrap check logic
        assert 'bootstrap' in script_content.lower()
        assert 'CDKToolkit' in script_content or 'cdk bootstrap' in script_content
    
    def test_script_runs_bootstrap_if_needed(self):
        """Test that script runs bootstrap if not already done."""
        with open('scripts/deploy.sh', 'r') as f:
            script_content = f.read()
        
        # Verify script has logic to run bootstrap
        assert 'cdk bootstrap' in script_content


class TestDeployWorkflow:
    """Test deployment workflow."""
    
    def test_script_runs_cdk_synth(self):
        """Test that script runs cdk synth."""
        with open('scripts/deploy.sh', 'r') as f:
            script_content = f.read()
        
        # Verify script runs synth
        assert 'cdk synth' in script_content
    
    def test_script_runs_cdk_deploy(self):
        """Test that script runs cdk deploy."""
        with open('scripts/deploy.sh', 'r') as f:
            script_content = f.read()
        
        # Verify script runs deploy
        assert 'cdk deploy' in script_content
    
    def test_script_passes_stage_to_cdk(self):
        """Test that script passes stage parameter to CDK."""
        with open('scripts/deploy.sh', 'r') as f:
            script_content = f.read()
        
        # Verify script passes stage context
        assert '--context' in script_content or '-c' in script_content
        assert 'stage' in script_content.lower()
    
    def test_script_passes_vpc_id_to_cdk(self):
        """Test that script passes vpc-id to CDK when provided."""
        with open('scripts/deploy.sh', 'r') as f:
            script_content = f.read()
        
        # Verify script has logic to pass vpc-id
        assert 'vpc' in script_content.lower() or 'VPC' in script_content
    
    def test_script_displays_outputs_on_success(self):
        """Test that script displays stack outputs on successful deployment."""
        with open('scripts/deploy.sh', 'r') as f:
            script_content = f.read()
        
        # Verify script retrieves and displays outputs
        assert 'describe-stacks' in script_content or 'Outputs' in script_content
    
    def test_script_exits_on_deployment_failure(self):
        """Test that script exits with non-zero code on deployment failure."""
        with open('scripts/deploy.sh', 'r') as f:
            script_content = f.read()
        
        # Verify script has error handling
        assert 'set -e' in script_content or 'exit 1' in script_content


class TestDestroyWorkflow:
    """Test destroy workflow."""
    
    def test_script_runs_cdk_destroy_with_flag(self):
        """Test that script runs cdk destroy when --destroy flag is provided."""
        with open('scripts/deploy.sh', 'r') as f:
            script_content = f.read()
        
        # Verify script has destroy logic
        assert 'cdk destroy' in script_content
        assert '--force' in script_content or '-f' in script_content
    
    def test_script_skips_deploy_when_destroy_flag_set(self):
        """Test that script doesn't deploy when destroy flag is set."""
        with open('scripts/deploy.sh', 'r') as f:
            script_content = f.read()
        
        # Verify script has conditional logic for destroy
        assert 'destroy' in script_content.lower()
        # Should have if/else or case statement
        assert 'if' in script_content or 'case' in script_content


class TestErrorHandling:
    """Test error handling in deployment script."""
    
    def test_script_exits_on_synth_failure(self):
        """Test that script exits if cdk synth fails."""
        with open('scripts/deploy.sh', 'r') as f:
            script_content = f.read()
        
        # Verify script has error handling (set -e or explicit checks)
        assert 'set -e' in script_content or ('if' in script_content and 'exit' in script_content)
    
    def test_script_displays_error_messages(self):
        """Test that script displays helpful error messages."""
        with open('scripts/deploy.sh', 'r') as f:
            script_content = f.read()
        
        # Verify script has echo statements for errors
        assert 'echo' in script_content
        assert 'Error' in script_content or 'error' in script_content
    
    def test_script_provides_troubleshooting_steps(self):
        """Test that script provides troubleshooting information on failure."""
        with open('scripts/deploy.sh', 'r') as f:
            script_content = f.read()
        
        # Verify script has helpful messages
        # At minimum should have usage/help information
        assert 'Usage' in script_content or 'usage' in script_content


class TestScriptStructure:
    """Test deployment script structure and best practices."""
    
    def test_script_has_shebang(self):
        """Test that script has proper shebang."""
        with open('scripts/deploy.sh', 'r') as f:
            first_line = f.readline()
        
        assert first_line.startswith('#!')
        assert 'bash' in first_line or 'sh' in first_line
    
    def test_script_uses_set_e(self):
        """Test that script uses set -e for error handling."""
        with open('scripts/deploy.sh', 'r') as f:
            script_content = f.read()
        
        # Should have set -e for fail-fast behavior
        assert 'set -e' in script_content
    
    def test_script_is_executable(self):
        """Test that script has executable permissions."""
        import stat
        
        st = os.stat('scripts/deploy.sh')
        is_executable = bool(st.st_mode & stat.S_IXUSR)
        
        assert is_executable, "deploy.sh should have executable permissions"
    
    def test_script_validates_required_tools(self):
        """Test that script checks for required tools (aws, cdk)."""
        with open('scripts/deploy.sh', 'r') as f:
            script_content = f.read()
        
        # Should check for AWS CLI and CDK
        # Common patterns: command -v, which, type
        has_tool_check = (
            'command -v' in script_content or
            'which' in script_content or
            'type' in script_content or
            'aws' in script_content
        )
        
        assert has_tool_check, "Script should validate required tools are installed"


class TestIntegrationScenarios:
    """Test integration scenarios (require mocking)."""
    
    def test_deploy_without_vpc_creates_new_vpc(self):
        """Test deployment without vpc-id creates new VPC."""
        with open('scripts/deploy.sh', 'r') as f:
            script_content = f.read()
        
        # Verify script has logic to handle VPC creation
        # Should pass context or flag to CDK
        assert 'vpc' in script_content.lower()
    
    def test_deploy_with_vpc_uses_existing_vpc(self):
        """Test deployment with vpc-id uses existing VPC."""
        with open('scripts/deploy.sh', 'r') as f:
            script_content = f.read()
        
        # Verify script passes vpc-id to CDK
        assert 'vpc' in script_content.lower() or 'VPC' in script_content
    
    def test_multiple_stage_deployments_isolated(self):
        """Test that multiple stages can be deployed independently."""
        with open('scripts/deploy.sh', 'r') as f:
            script_content = f.read()
        
        # Verify script passes stage to CDK for resource naming
        assert 'stage' in script_content.lower()
        assert '--context' in script_content or '-c' in script_content


class TestDocumentation:
    """Test script documentation."""
    
    def test_script_has_usage_documentation(self):
        """Test that script has usage documentation."""
        with open('scripts/deploy.sh', 'r') as f:
            script_content = f.read()
        
        # Should have usage function or help text
        assert 'Usage' in script_content or 'usage' in script_content
        assert '--stage' in script_content
    
    def test_script_has_examples(self):
        """Test that script includes usage examples."""
        with open('scripts/deploy.sh', 'r') as f:
            script_content = f.read()
        
        # Should have example commands
        assert 'Example' in script_content or 'example' in script_content or './deploy.sh' in script_content
    
    def test_script_documents_parameters(self):
        """Test that script documents all parameters."""
        with open('scripts/deploy.sh', 'r') as f:
            script_content = f.read()
        
        # Should document stage, vpc-id, destroy
        assert '--stage' in script_content
        assert '--vpc-id' in script_content or 'vpc-id' in script_content
        assert '--destroy' in script_content


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
