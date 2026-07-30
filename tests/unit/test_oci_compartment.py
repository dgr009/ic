#!/usr/bin/env python3
"""
Unit tests for OCI compartment tree module.

This module tests the compartment tree builder and renderer functionality.
"""

import unittest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime

# Import modules to test
from ic.platforms.oci.compartment.info import CompartmentTreeBuilder, CompartmentTreeRenderer


class TestCompartmentTreeBuilder(unittest.TestCase):
    """Test cases for CompartmentTreeBuilder class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.builder = CompartmentTreeBuilder()
    
    @patch('ic.platforms.oci.compartment.info.get_compartments')
    def test_build_compartment_tree_success(self, mock_get_compartments):
        """Test successful compartment tree building."""
        # Mock compartment data
        mock_compartments = [
            {
                'id': 'ocid1.compartment.oc1..child1',
                'name': 'Development',
                'description': 'Development environment',
                'compartment_id': 'ocid1.tenancy.oc1..root',
                'lifecycle_state': 'ACTIVE',
                'time_created': datetime.now()
            },
            {
                'id': 'ocid1.compartment.oc1..child2',
                'name': 'Production',
                'description': 'Production environment',
                'compartment_id': 'ocid1.tenancy.oc1..root',
                'lifecycle_state': 'ACTIVE',
                'time_created': datetime.now()
            },
            {
                'id': 'ocid1.compartment.oc1..grandchild',
                'name': 'Dev-Testing',
                'description': 'Testing sub-compartment',
                'compartment_id': 'ocid1.compartment.oc1..child1',
                'lifecycle_state': 'ACTIVE',
                'time_created': datetime.now()
            }
        ]
        
        mock_get_compartments.return_value = mock_compartments
        
        mock_identity_client = MagicMock()
        tenancy_ocid = 'ocid1.tenancy.oc1..root'
        
        result = self.builder.build_compartment_tree(mock_identity_client, tenancy_ocid)
        
        # Verify tree structure
        self.assertEqual(result['id'], tenancy_ocid)
        self.assertEqual(result['name'], 'Root Compartment (Tenancy)')
        self.assertEqual(len(result['children']), 2)  # Development and Production
        
        # Find Development compartment
        dev_compartment = next(c for c in result['children'] if c['name'] == 'Development')
        self.assertEqual(len(dev_compartment['children']), 1)  # Dev-Testing
        
        # Find Production compartment
        prod_compartment = next(c for c in result['children'] if c['name'] == 'Production')
        self.assertEqual(len(prod_compartment['children']), 0)  # No children
    
    @patch('ic.platforms.oci.compartment.info.get_compartments')
    def test_build_compartment_tree_error(self, mock_get_compartments):
        """Test handling of errors during tree building."""
        mock_get_compartments.side_effect = Exception("API Error")
        
        mock_identity_client = MagicMock()
        tenancy_ocid = 'ocid1.tenancy.oc1..root'
        
        result = self.builder.build_compartment_tree(mock_identity_client, tenancy_ocid)
        
        # Should return empty dict on error
        self.assertEqual(result, {})
    
    def test_organize_compartments_by_hierarchy(self):
        """Test compartment hierarchy organization."""
        compartments = [
            {
                'id': 'ocid1.compartment.oc1..child1',
                'name': 'Development',
                'description': 'Dev environment',
                'compartment_id': 'ocid1.tenancy.oc1..root',
                'lifecycle_state': 'ACTIVE',
                'time_created': datetime.now()
            },
            {
                'id': 'ocid1.compartment.oc1..grandchild',
                'name': 'Dev-Testing',
                'description': 'Testing',
                'compartment_id': 'ocid1.compartment.oc1..child1',
                'lifecycle_state': 'ACTIVE',
                'time_created': datetime.now()
            }
        ]
        
        tenancy_ocid = 'ocid1.tenancy.oc1..root'
        
        result = self.builder.organize_compartments_by_hierarchy(compartments, tenancy_ocid)
        
        # Verify root structure
        self.assertEqual(result['id'], tenancy_ocid)
        self.assertEqual(len(result['children']), 1)
        
        # Verify child structure
        child = result['children'][0]
        self.assertEqual(child['name'], 'Development')
        self.assertEqual(len(child['children']), 1)
        
        # Verify grandchild structure
        grandchild = child['children'][0]
        self.assertEqual(grandchild['name'], 'Dev-Testing')
        self.assertEqual(len(grandchild['children']), 0)


class TestCompartmentTreeRenderer(unittest.TestCase):
    """Test cases for CompartmentTreeRenderer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.renderer = CompartmentTreeRenderer()
    
    def test_render_tree_empty(self):
        """Test rendering with empty tree data."""
        with patch.object(self.renderer, 'console') as mock_console:
            self.renderer.render_tree({})
            
            # Verify console.print was called with appropriate message
            mock_console.print.assert_called_with("📋 No compartment data available.")
    
    @patch('ic.platforms.oci.compartment.info.Tree')
    def test_render_tree_with_data(self, mock_tree_class):
        """Test rendering with compartment tree data."""
        mock_tree = MagicMock()
        mock_tree_class.return_value = mock_tree
        
        tree_data = {
            'id': 'ocid1.tenancy.oc1..root',
            'name': 'Root Compartment (Tenancy)',
            'description': 'Root compartment',
            'parent_id': None,
            'lifecycle_state': 'ACTIVE',
            'time_created': None,
            'children': [
                {
                    'id': 'ocid1.compartment.oc1..child1',
                    'name': 'Development',
                    'description': 'Dev environment',
                    'parent_id': 'ocid1.tenancy.oc1..root',
                    'lifecycle_state': 'ACTIVE',
                    'time_created': datetime.now(),
                    'children': []
                }
            ]
        }
        
        with patch.object(self.renderer, 'console') as mock_console:
            self.renderer.render_tree(tree_data)
            
            # Verify Tree was created and console.print was called
            mock_tree_class.assert_called_once()
            mock_console.print.assert_called()
            
            # Check that summary information is printed
            call_args = [str(arg) for call in mock_console.print.call_args_list for arg in call.args]
            summary_found = any('Total compartments: 1' in arg for arg in call_args)
            self.assertTrue(summary_found)
    
    def test_format_compartment_node(self):
        """Test compartment node formatting."""
        compartment = {
            'name': 'Test Compartment',
            'id': 'ocid1.compartment.oc1..test',
            'lifecycle_state': 'ACTIVE'
        }
        
        result = self.renderer.format_compartment_node(compartment)
        
        # Verify Text object is returned (we can't easily test Rich Text content)
        from rich.text import Text
        self.assertIsInstance(result, Text)
    
    def test_format_compartment_node_inactive(self):
        """Test compartment node formatting for inactive compartment."""
        compartment = {
            'name': 'Inactive Compartment',
            'id': 'ocid1.compartment.oc1..inactive',
            'lifecycle_state': 'INACTIVE'
        }
        
        result = self.renderer.format_compartment_node(compartment)
        
        # Verify Text object is returned
        from rich.text import Text
        self.assertIsInstance(result, Text)
    
    def test_count_compartments(self):
        """Test compartment counting."""
        compartment_tree = {
            'id': 'root',
            'children': [
                {
                    'id': 'child1',
                    'children': [
                        {'id': 'grandchild1', 'children': []},
                        {'id': 'grandchild2', 'children': []}
                    ]
                },
                {
                    'id': 'child2',
                    'children': []
                }
            ]
        }
        
        count = self.renderer._count_compartments(compartment_tree)
        
        # Should count root + 2 children + 2 grandchildren = 5
        self.assertEqual(count, 5)


if __name__ == '__main__':
    unittest.main()