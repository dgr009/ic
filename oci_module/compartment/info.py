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


class CompartmentTreeBuilder:
    """Builds hierarchical compartment structure from OCI API."""
    
    def __init__(self):
        self.console = Console()
    
    def build_compartment_tree(self, identity_client: oci.identity.IdentityClient, tenancy_ocid: str) -> Dict[str, Any]:
        """
        Build compartment tree structure from OCI API.
        
        Args:
            identity_client: OCI Identity client
            tenancy_ocid: Tenancy OCID
            
        Returns:
            Dictionary representing the compartment tree structure
        """
        from rich.progress import Progress, SpinnerColumn, TextColumn
        import time
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                
                # Fetch compartments
                task = progress.add_task("Fetching compartments from OCI...", total=None)
                start_time = time.time()
                
                compartments = get_compartments(identity_client, tenancy_ocid)
                
                progress.update(task, description=f"Building hierarchy for {len(compartments)} compartments...")
                
                # Organize compartments by hierarchy
                tree_data = self.organize_compartments_by_hierarchy(compartments, tenancy_ocid)
                
                # Calculate processing time
                processing_time = time.time() - start_time
                progress.update(task, description=f"Completed in {processing_time:.2f}s")
                progress.stop()
                
                return tree_data
            
        except Exception as e:
            self.console.print(f"❌ Failed to build compartment tree: {e}")
            return {}
    
    def organize_compartments_by_hierarchy(self, compartments: List[Dict[str, Any]], tenancy_ocid: str) -> Dict[str, Any]:
        """
        Organize compartments into hierarchical structure.
        
        Args:
            compartments: List of compartment data from OCI API
            tenancy_ocid: Tenancy OCID (root compartment)
            
        Returns:
            Dictionary representing hierarchical compartment structure
        """
        # Create compartment lookup by OCID
        compartment_lookup = {}
        for comp in compartments:
            compartment_lookup[comp['id']] = {
                'id': comp['id'],
                'name': comp['name'],
                'description': comp.get('description', ''),
                'parent_id': comp.get('compartment_id'),
                'lifecycle_state': comp.get('lifecycle_state', 'ACTIVE'),
                'time_created': comp.get('time_created'),
                'children': []
            }
        
        # Add root compartment (tenancy)
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
        
        # Build parent-child relationships
        for comp_id, comp_data in compartment_lookup.items():
            parent_id = comp_data['parent_id']
            if parent_id and parent_id in compartment_lookup:
                compartment_lookup[parent_id]['children'].append(comp_data)
        
        return root_compartment


class CompartmentTreeRenderer:
    """Renders compartment tree structure with Rich formatting."""
    
    def __init__(self):
        self.console = Console()
    
    def render_tree(self, tree_data: Dict[str, Any]) -> None:
        """
        Render compartment tree using Rich Tree widget.
        
        Args:
            tree_data: Hierarchical compartment data
        """
        if not tree_data:
            self.console.print("📋 No compartment data available.")
            return
        
        # Create Rich tree
        tree = Tree(self.format_compartment_node(tree_data))
        
        # Add child compartments recursively
        self._add_children_to_tree(tree, tree_data['children'])
        
        # Display the tree
        self.console.print(tree)
        
        # Display summary
        total_compartments = self._count_compartments(tree_data) - 1  # Exclude root
        self.console.print(f"\n📊 Total compartments: {total_compartments}")
    
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