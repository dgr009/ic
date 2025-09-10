"""
OCI Compartment tree builder and renderer for hierarchical visualization.

This module provides classes to build and display OCI compartment
hierarchies in a tree structure format with Rich formatting.
"""

import oci
from typing import Dict, List, Any, Optional
from rich.console import Console
from rich.tree import Tree
from rich.text import Text
from datetime import datetime

from ..common.utils import get_compartments
from common.progress_decorator import progress_bar, ManualProgress


class CompartmentTreeBuilder:
    """Builds hierarchical compartment structure from OCI API."""
    
    def __init__(self):
        self.console = Console()
    
    @progress_bar("Building OCI compartment tree")
    def build_compartment_tree(self, identity_client: oci.identity.IdentityClient, tenancy_ocid: str) -> Dict[str, Any]:
        """
        Build compartment tree structure from OCI API.
        
        Args:
            identity_client: OCI Identity client
            tenancy_ocid: Tenancy OCID
            
        Returns:
            Dictionary representing the compartment tree structure
        """
        import time
        
        try:
            with ManualProgress("Building compartment hierarchy", total=3) as progress:
                
                # Step 1: Fetch compartments from OCI API
                progress.update("Fetching compartments from OCI Identity API")
                start_time = time.time()
                compartments = get_compartments(identity_client, tenancy_ocid)
                progress.advance(1)
                
                # Step 2: Organize compartments by hierarchy
                progress.update(f"Building hierarchy for {len(compartments)} compartments")
                tree_data = self.organize_compartments_by_hierarchy(compartments, tenancy_ocid)
                progress.advance(1)
                
                # Step 3: Finalize tree structure
                processing_time = time.time() - start_time
                progress.update(f"Completed compartment tree in {processing_time:.2f}s")
                progress.advance(1)
                
                return tree_data
            
        except Exception as e:
            self.console.print(f"❌ Failed to build compartment tree: {e}")
            return {}
    
    def organize_compartments_by_hierarchy(self, compartments: List[Any], tenancy_ocid: str) -> Dict[str, Any]:
        """
        Organize compartments into hierarchical structure.
        
        Args:
            compartments: List of compartment objects from OCI API
            tenancy_ocid: Tenancy OCID (root compartment)
            
        Returns:
            Dictionary representing hierarchical compartment structure
        """
        with ManualProgress("Organizing compartment hierarchy", total=3) as progress:
            
            # Step 1: Create compartment lookup by OCID
            progress.update(f"Creating lookup table for {len(compartments)} compartments")
            compartment_lookup = {}
            for comp in compartments:
                # Handle both OCI compartment objects and dictionaries (for testing)
                if isinstance(comp, dict):
                    # Dictionary format (used in tests)
                    compartment_lookup[comp['id']] = {
                        'id': comp['id'],
                        'name': comp['name'],
                        'description': comp.get('description', ''),
                        'parent_id': comp.get('compartment_id', None),
                        'lifecycle_state': comp.get('lifecycle_state', 'ACTIVE'),
                        'time_created': comp.get('time_created', None),
                        'children': []
                    }
                else:
                    # OCI compartment object format (real API)
                    compartment_lookup[comp.id] = {
                        'id': comp.id,
                        'name': comp.name,
                        'description': getattr(comp, 'description', ''),
                        'parent_id': getattr(comp, 'compartment_id', None),
                        'lifecycle_state': getattr(comp, 'lifecycle_state', 'ACTIVE'),
                        'time_created': getattr(comp, 'time_created', None),
                        'children': []
                    }
            progress.advance(1)
            
            # Step 2: Add root compartment (tenancy)
            progress.update("Adding root compartment (tenancy)")
            root_compartment = {
                'id': tenancy_ocid,
                'name': 'Root Compartment (Tenancy)',
                'description': 'Root compartment of the tenancy',
                'parent_id': None,
                'lifecycle_state': 'ACTIVE',
                'time_created': None,
                'children': []
            }
            compartment_lookup[tenancy_ocid] = root_compartment
            progress.advance(1)
            
            # Step 3: Build parent-child relationships
            progress.update("Building parent-child relationships")
            relationship_count = 0
            for comp_id, comp_data in compartment_lookup.items():
                parent_id = comp_data['parent_id']
                if parent_id and parent_id in compartment_lookup:
                    compartment_lookup[parent_id]['children'].append(comp_data)
                    relationship_count += 1
            
            progress.update(f"Built {relationship_count} parent-child relationships")
            progress.advance(1)
        
        return root_compartment


class CompartmentTreeRenderer:
    """Renders compartment tree structure with Rich formatting."""
    
    def __init__(self):
        self.console = Console()
    
    @progress_bar("Rendering compartment tree")
    def render_tree(self, tree_data: Dict[str, Any]) -> None:
        """
        Render compartment tree using Rich Tree widget.
        
        Args:
            tree_data: Hierarchical compartment data
        """
        if not tree_data:
            self.console.print("📋 No compartment data available.")
            return
        
        with ManualProgress("Rendering compartment tree display", total=4) as progress:
            
            # Step 1: Create Rich tree root
            progress.update("Creating tree root node")
            tree = Tree(self.format_compartment_node(tree_data))
            progress.advance(1)
            
            # Step 2: Add child compartments recursively
            progress.update(f"Adding {len(tree_data['children'])} child compartments")
            self._add_children_to_tree(tree, tree_data['children'])
            progress.advance(1)
            
            # Step 3: Display the tree
            progress.update("Displaying compartment tree")
            self.console.print(tree)
            progress.advance(1)
            
            # Step 4: Display summary statistics
            progress.update("Calculating tree statistics")
            total_compartments = self._count_compartments(tree_data) - 1  # Exclude root
            self.console.print(f"\n📊 Total compartments: {total_compartments}")
            progress.advance(1)
    
    def _add_children_to_tree(self, parent_node: Tree, children: List[Dict[str, Any]]) -> None:
        """
        Recursively add child compartments to tree node.
        
        Args:
            parent_node: Parent tree node
            children: List of child compartment data
        """
        for child in children:
            child_node = parent_node.add(self.format_compartment_node(child))
            if child['children']:
                self._add_children_to_tree(child_node, child['children'])
    
    def format_compartment_node(self, compartment: Dict[str, Any]) -> Text:
        """
        Format compartment node with name and OCID.
        
        Args:
            compartment: Compartment data dictionary
            
        Returns:
            Rich Text object with formatted compartment information
        """
        name = compartment['name']
        ocid = compartment['id']
        state = compartment['lifecycle_state']
        
        # Create formatted text
        text = Text()
        text.append(name, style="bold cyan")
        
        # Add state indicator if not active
        if state != 'ACTIVE':
            text.append(f" [{state}]", style="red")
        
        # Add OCID in gray
        text.append(f" ({ocid})", style="dim")
        
        return text
    
    def _count_compartments(self, compartment: Dict[str, Any]) -> int:
        """
        Count total number of compartments in tree.
        
        Args:
            compartment: Root compartment data
            
        Returns:
            Total count of compartments
        """
        count = 1  # Count current compartment
        for child in compartment['children']:
            count += self._count_compartments(child)
        return count