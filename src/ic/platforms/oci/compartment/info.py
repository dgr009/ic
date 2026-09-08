"""
OCI Compartment tree builder and renderer for hierarchical visualization.

This module provides classes to build and display OCI compartment
hierarchies in a tree structure format with Rich formatting.
"""

import oci
from typing import Dict, List, Any
from rich.console import Console
from rich.tree import Tree
from rich.text import Text

from ..common.utils import get_compartments


###############################################################################
# CLI 인자 정의
###############################################################################
def add_arguments(parser):
    """Compartment Info에 필요한 인자 추가"""
    parser.add_argument(
        "-f", "--format",
        choices=["tree", "list"],
        default="tree",
        help="출력 형식 (tree: 계층 구조, list: 평면 목록)"
    )


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
        try:
            # Fetch compartments from OCI API
            compartments = get_compartments(identity_client, tenancy_ocid)
            
            # Organize compartments by hierarchy
            tree_data = self.organize_compartments_by_hierarchy(compartments, tenancy_ocid)
            
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
        # Create compartment lookup by OCID
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
        for comp_data in compartment_lookup.values():
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
        
        # Create Rich tree root
        tree = Tree(self.format_compartment_node(tree_data))
        
        # Add child compartments recursively
        self._add_children_to_tree(tree, tree_data['children'])
        
        # Display the tree with a newline before for clean output
        self.console.print()
        self.console.print(tree)
        
        # Display summary statistics
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


from ic.core.interfaces import BaseCommand, CommandResult


def render_compartment_view(tree_data: Dict[str, Any], format_type: str = "tree", verbose: bool = False) -> None:
    """Render compartment data as tree or list."""
    console = Console()
    if not tree_data:
        console.print("📋 No compartment data available.")
        return
    if format_type == "tree":
        renderer = CompartmentTreeRenderer()
        renderer.render_tree(tree_data)
    else:
        console.print()
        _render_list(tree_data, console)


class OciCompartmentInfoCommand(BaseCommand):
    """OCI Compartment hierarchy information command."""

    @classmethod
    def add_arguments(cls, parser):
        cls.add_common_arguments(parser)
        parser.add_argument(
            "-f", "--format",
            choices=["tree", "list"],
            default="tree",
            help="출력 형식 (tree: 계층 구조, list: 평면 목록)"
        )

    def execute(self, args, config=None) -> CommandResult:
        console = Console()
        try:
            oci_config = oci.config.from_file()
            identity_client = oci.identity.IdentityClient(oci_config)
            tenancy_ocid = oci_config["tenancy"]

            builder = CompartmentTreeBuilder()
            tree_data = builder.build_compartment_tree(identity_client, tenancy_ocid)

            fmt = getattr(args, "format", "tree")
            return CommandResult(
                data=tree_data,
                table_renderer=lambda data, verbose=False: render_compartment_view(data, format_type=fmt, verbose=verbose),
            )
        except oci.exceptions.ConfigFileNotFound:
            console.print("❌ OCI 설정 파일을 찾을 수 없습니다. ~/.oci/config 파일을 확인하세요.")
            return CommandResult(data={}, success=False, error="OCI config not found")
        except oci.exceptions.InvalidConfig as e:
            console.print(f"❌ OCI 설정이 올바르지 않습니다: {e}")
            return CommandResult(data={}, success=False, error=str(e))
        except Exception as e:
            console.print(f"❌ Compartment 조회 중 오류 발생: {e}")
            return CommandResult(data={}, success=False, error=str(e))


def main(args, config=None):
    """OCI Compartment 정보를 조회하고 출력합니다."""
    OciCompartmentInfoCommand().run(args, config)


def _render_list(tree_data: Dict[str, Any], console: Console, level: int = 0) -> None:
    """
    Compartment를 평면 목록 형식으로 출력합니다.
    
    Args:
        tree_data: Compartment 트리 데이터
        console: Rich Console 객체
        level: 들여쓰기 레벨
    """
    indent = "  " * level
    name = tree_data['name']
    ocid = tree_data['id']
    state = tree_data['lifecycle_state']
    
    # 상태에 따른 아이콘
    state_icon = "✓" if state == "ACTIVE" else "✗"
    
    console.print(f"{indent}{state_icon} {name}")
    console.print(f"{indent}  OCID: {ocid}", style="dim")
    
    # 자식 compartment 재귀 출력
    for child in tree_data.get('children', []):
        _render_list(child, console, level + 1)