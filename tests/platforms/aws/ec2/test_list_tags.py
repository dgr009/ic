"""
Unit tests for AWS EC2 list_tags module
"""
import pytest
from unittest.mock import Mock, patch, MagicMock


class TestEC2ListTags:
    """Test cases for EC2 list_tags functionality"""
    
    def test_get_tag_keys_from_config(self):
        """Test tag keys are loaded from config"""
        with patch('src.ic.platforms.aws.ec2.list_tags.config', {
            'aws': {
                'tags': {
                    'required': ['Name', 'User', 'Team'],
                    'optional': ['Environment']
                }
            }
        }):
            from src.ic.platforms.aws.ec2.list_tags import get_tag_keys
            tag_keys = get_tag_keys()
            assert 'Name' in tag_keys
            assert 'User' in tag_keys
            assert 'Team' in tag_keys
            assert 'Environment' in tag_keys
    
    def test_get_tag_keys_fallback_to_env(self):
        """Test tag keys fallback to environment variables"""
        with patch('src.ic.platforms.aws.ec2.list_tags.config', {}):
            with patch.dict('os.environ', {
                'REQUIRED_TAGS': 'User,Team',
                'OPTIONAL_TAGS': 'Service'
            }):
                from src.ic.platforms.aws.ec2.list_tags import get_tag_keys
                tag_keys = get_tag_keys()
                assert 'User' in tag_keys
                assert 'Team' in tag_keys
                assert 'Service' in tag_keys
    
    @pytest.mark.ci_safe
    def test_add_arguments(self):
        """Test CLI argument parser setup"""
        from src.ic.platforms.aws.ec2.list_tags import add_arguments
        parser = Mock()
        add_arguments(parser)
        assert parser.add_argument.called
