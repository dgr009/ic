"""
Documentation organizer module for IC.

This module provides functionality to organize and restructure documentation files.
"""

import os
import re
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class DocsOrganizer:
    """
    Organizes documentation files into a structured docs directory.
    """
    
    def __init__(self):
        """Initialize DocsOrganizer."""
        self.docs_dir = Path("docs")
        self.reorganization_history: List[Dict[str, Any]] = []
        self.link_updates: List[Dict[str, Any]] = []
    
    def reorganize_docs(self) -> bool:
        """
        Reorganize all documentation files into docs directory structure.
        
        Returns:
            True if reorganization was successful
        """
        try:
            # Create docs directory structure
            self._create_docs_structure()
            
            # Find all markdown files
            md_files = self._find_markdown_files()
            
            # Categorize and move files
            moved_files = []
            for md_file in md_files:
                new_location = self._categorize_and_move_file(md_file)
                if new_location:
                    moved_files.append({
                        "original_path": str(md_file),
                        "new_path": str(new_location),
                        "category": self._get_file_category(md_file),
                        "size": md_file.stat().st_size if md_file.exists() else 0
                    })
            
            # Update links in moved files
            self._update_links_in_files(moved_files)
            
            # Record reorganization
            self.reorganization_history.extend(moved_files)
            
            logger.info(f"Reorganized {len(moved_files)} documentation files")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reorganize documentation: {e}")
            return False
    
    def _create_docs_structure(self):
        """Create the documentation directory structure."""
        structure = {
            "docs": {
                "api": {},
                "guides": {
                    "installation": {},
                    "configuration": {},
                    "usage": {}
                },
                "reference": {
                    "aws": {},
                    "azure": {},
                    "gcp": {},
                    "oci": {},
                    "ssh": {}
                },
                "development": {
                    "architecture": {},
                    "contributing": {},
                    "testing": {}
                },
                "migration": {},
                "security": {},
                "troubleshooting": {}
            }
        }
        
        self._create_directory_structure(Path("."), structure)
    
    def _create_directory_structure(self, base_path: Path, structure: Dict[str, Any]):
        """Recursively create directory structure."""
        for name, subdirs in structure.items():
            dir_path = base_path / name
            dir_path.mkdir(exist_ok=True)
            
            if isinstance(subdirs, dict) and subdirs:
                self._create_directory_structure(dir_path, subdirs)
    
    def _find_markdown_files(self) -> List[Path]:
        """Find all markdown files in the project."""
        md_files = []
        
        # Search patterns
        search_paths = [
            Path(".").glob("*.md"),
            Path(".").glob("**/*.md")
        ]
        
        # Exclude certain directories
        exclude_dirs = {".git", "node_modules", "__pycache__", ".pytest_cache", "venv", "env"}
        
        for pattern in search_paths:
            for md_file in pattern:
                # Skip if in excluded directory
                if any(excluded in md_file.parts for excluded in exclude_dirs):
                    continue
                
                # Skip if already in docs directory
                if "docs" in md_file.parts and md_file.parts.index("docs") == 0:
                    continue
                
                md_files.append(md_file)
        
        # Remove duplicates
        return list(set(md_files))
    
    def _categorize_and_move_file(self, md_file: Path) -> Optional[Path]:
        """Categorize a markdown file and move it to appropriate location."""
        if not md_file.exists():
            return None
        
        try:
            # Determine category based on filename and content
            category = self._get_file_category(md_file)
            
            # Determine target directory
            target_dir = self._get_target_directory(category, md_file)
            
            # Generate new filename
            new_filename = self._generate_new_filename(md_file, category)
            
            # Move file
            new_path = target_dir / new_filename
            
            # Ensure target directory exists
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Handle filename conflicts
            counter = 1
            original_new_path = new_path
            while new_path.exists():
                stem = original_new_path.stem
                suffix = original_new_path.suffix
                new_path = target_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            
            shutil.move(str(md_file), str(new_path))
            logger.debug(f"Moved {md_file} to {new_path}")
            
            return new_path
            
        except Exception as e:
            logger.warning(f"Failed to move {md_file}: {e}")
            return None
    
    def _get_file_category(self, md_file: Path) -> str:
        """Determine the category of a markdown file."""
        filename = md_file.name.lower()
        
        # Read first few lines to understand content
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read(1000).lower()  # First 1000 characters
        except Exception:
            content = ""
        
        # Categorize based on filename patterns
        if filename in ['readme.md', 'readme.rst']:
            return "main"
        elif 'install' in filename or 'setup' in filename:
            return "installation"
        elif 'config' in filename or 'configuration' in filename:
            return "configuration"
        elif 'api' in filename or 'reference' in filename:
            return "api"
        elif 'guide' in filename or 'tutorial' in filename or 'howto' in filename:
            return "guides"
        elif 'security' in filename or 'security' in content:
            return "security"
        elif 'migration' in filename or 'migrate' in filename:
            return "migration"
        elif 'troubleshoot' in filename or 'faq' in filename or 'problem' in filename:
            return "troubleshooting"
        elif 'develop' in filename or 'contribute' in filename or 'architecture' in filename:
            return "development"
        elif any(cloud in filename for cloud in ['aws', 'azure', 'gcp', 'oci', 'ssh']):
            # Cloud-specific documentation
            for cloud in ['aws', 'azure', 'gcp', 'oci', 'ssh']:
                if cloud in filename:
                    return f"reference_{cloud}"
            return "reference"
        elif 'test' in filename:
            return "development_testing"
        else:
            return "general"
    
    def _get_target_directory(self, category: str, md_file: Path) -> Path:
        """Get target directory based on category."""
        base_docs = self.docs_dir
        
        category_mapping = {
            "main": base_docs,
            "installation": base_docs / "guides" / "installation",
            "configuration": base_docs / "guides" / "configuration",
            "api": base_docs / "api",
            "guides": base_docs / "guides" / "usage",
            "security": base_docs / "security",
            "migration": base_docs / "migration",
            "troubleshooting": base_docs / "troubleshooting",
            "development": base_docs / "development",
            "development_testing": base_docs / "development" / "testing",
            "reference_aws": base_docs / "reference" / "aws",
            "reference_azure": base_docs / "reference" / "azure",
            "reference_gcp": base_docs / "reference" / "gcp",
            "reference_oci": base_docs / "reference" / "oci",
            "reference_ssh": base_docs / "reference" / "ssh",
            "reference": base_docs / "reference",
            "general": base_docs
        }
        
        return category_mapping.get(category, base_docs)
    
    def _generate_new_filename(self, md_file: Path, category: str) -> str:
        """Generate appropriate filename for the new location."""
        original_name = md_file.name
        
        # Special handling for README files
        if original_name.lower() in ['readme.md', 'readme.rst']:
            if category == "main":
                return "README.md"
            else:
                return "overview.md"
        
        # Clean up filename
        clean_name = original_name.lower()
        
        # Remove redundant category prefixes
        category_prefixes = ['aws-', 'azure-', 'gcp-', 'oci-', 'ssh-', 'config-', 'guide-', 'api-']
        for prefix in category_prefixes:
            if clean_name.startswith(prefix):
                clean_name = clean_name[len(prefix):]
                break
        
        # Ensure .md extension
        if not clean_name.endswith('.md'):
            clean_name = clean_name.rsplit('.', 1)[0] + '.md'
        
        return clean_name
    
    def _update_links_in_files(self, moved_files: List[Dict[str, Any]]):
        """Update links in moved files to reflect new structure."""
        # Create mapping of old paths to new paths
        path_mapping = {
            Path(f["original_path"]): Path(f["new_path"]) 
            for f in moved_files
        }
        
        # Update links in each moved file
        for file_info in moved_files:
            new_path = Path(file_info["new_path"])
            if new_path.exists():
                self._update_links_in_single_file(new_path, path_mapping)
    
    def _update_links_in_single_file(self, file_path: Path, path_mapping: Dict[Path, Path]):
        """Update links in a single file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Find markdown links: [text](path)
            link_pattern = r'\\[([^\\]]+)\\]\\(([^\\)]+)\\)'
            
            def replace_link(match):
                link_text = match.group(1)
                link_path = match.group(2)
                
                # Skip external links
                if link_path.startswith(('http://', 'https://', 'mailto:', '#')):
                    return match.group(0)
                
                # Convert to Path and resolve
                try:
                    old_link_path = Path(link_path)
                    
                    # Check if this path was moved
                    for old_path, new_path in path_mapping.items():
                        if old_link_path.name == old_path.name:
                            # Calculate relative path from current file to new location
                            relative_path = os.path.relpath(new_path, file_path.parent)
                            self.link_updates.append({
                                "file": str(file_path),
                                "old_link": link_path,
                                "new_link": relative_path
                            })
                            return f"[{link_text}]({relative_path})"
                    
                    return match.group(0)
                    
                except Exception:
                    return match.group(0)
            
            # Replace links
            content = re.sub(link_pattern, replace_link, content)
            
            # Write back if changed
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.debug(f"Updated links in {file_path}")
                
        except Exception as e:
            logger.warning(f"Failed to update links in {file_path}: {e}")
    
    def create_docs_index(self) -> bool:
        """
        Create a main index file for the documentation.
        
        Returns:
            True if index was created successfully
        """
        try:
            index_content = self._generate_docs_index_content()
            
            index_path = self.docs_dir / "README.md"
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(index_content)
            
            logger.info(f"Created documentation index at {index_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create documentation index: {e}")
            return False
    
    def _generate_docs_index_content(self) -> str:
        """Generate content for the documentation index."""
        content = """# IC Documentation

Welcome to the IC (Infrastructure CLI) documentation. This documentation has been reorganized to provide better structure and easier navigation.

## Quick Start

- [Installation Guide](guides/installation/)
- [Configuration Guide](guides/configuration/)
- [Usage Examples](guides/usage/)

## Documentation Structure

### 📚 Guides
Step-by-step instructions for common tasks:
- **[Installation](guides/installation/)** - How to install and set up IC
- **[Configuration](guides/configuration/)** - Configuration management and setup
- **[Usage](guides/usage/)** - Common usage patterns and examples

### 📖 Reference
Detailed reference documentation for each cloud provider:
- **[AWS](reference/aws/)** - Amazon Web Services integration
- **[Azure](reference/azure/)** - Microsoft Azure integration  
- **[GCP](reference/gcp/)** - Google Cloud Platform integration
- **[OCI](reference/oci/)** - Oracle Cloud Infrastructure integration
- **[SSH](reference/ssh/)** - SSH management and automation

### 🔧 Development
Information for developers and contributors:
- **[Architecture](development/architecture/)** - System architecture and design
- **[Contributing](development/contributing/)** - How to contribute to the project
- **[Testing](development/testing/)** - Testing guidelines and procedures

### 🔒 Security
Security-related documentation:
- **[Security Guide](security/)** - Security best practices and configuration

### 🚀 Migration
Migration guides and documentation:
- **[Migration Guide](migration/)** - Migrating from old configurations

### 🛠️ Troubleshooting
Common issues and solutions:
- **[Troubleshooting](troubleshooting/)** - Common problems and solutions

### 🔌 API Reference
API documentation and references:
- **[API Reference](api/)** - Detailed API documentation

## Recent Changes

This documentation has been reorganized as part of the IC configuration system migration. Key improvements include:

- **Better Structure**: Documentation is now organized by topic and purpose
- **Improved Navigation**: Clear hierarchy and cross-references
- **Updated Links**: All internal links have been updated to reflect the new structure
- **Consolidated Content**: Related documentation has been grouped together

## Getting Help

- Check the [Troubleshooting](troubleshooting/) section for common issues
- Review the relevant [Reference](reference/) documentation for your cloud provider
- Look at [Usage Examples](guides/usage/) for practical examples

## Contributing to Documentation

See the [Contributing Guide](development/contributing/) for information on how to improve this documentation.

---

*This documentation was automatically reorganized on """ + f"{datetime.now().strftime('%Y-%m-%d')}*"
        
        return content
    
    def create_reorganization_history_document(self) -> bool:
        """
        Create a document recording the documentation reorganization.
        
        Returns:
            True if document was created successfully
        """
        try:
            history_content = self._generate_reorganization_history_content()
            
            history_path = self.docs_dir / "reorganization_history.md"
            with open(history_path, 'w', encoding='utf-8') as f:
                f.write(history_content)
            
            logger.info(f"Created reorganization history at {history_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create reorganization history: {e}")
            return False
    
    def _generate_reorganization_history_content(self) -> str:
        """Generate reorganization history document content."""
        content = """# Documentation Reorganization History

This document records the reorganization of IC documentation files into a structured format.

## Overview

The documentation has been reorganized to improve discoverability and maintainability. Files have been categorized and moved to appropriate directories within the `docs/` folder.

## New Structure

```
docs/
├── README.md                    # Main documentation index
├── api/                         # API reference documentation
├── guides/                      # User guides and tutorials
│   ├── installation/           # Installation guides
│   ├── configuration/          # Configuration guides
│   └── usage/                  # Usage examples
├── reference/                   # Reference documentation
│   ├── aws/                    # AWS-specific documentation
│   ├── azure/                  # Azure-specific documentation
│   ├── gcp/                    # GCP-specific documentation
│   ├── oci/                    # OCI-specific documentation
│   └── ssh/                    # SSH-specific documentation
├── development/                 # Development documentation
│   ├── architecture/           # Architecture documentation
│   ├── contributing/           # Contributing guidelines
│   └── testing/               # Testing documentation
├── migration/                   # Migration guides
├── security/                    # Security documentation
└── troubleshooting/            # Troubleshooting guides
```

## File Movements

"""
        
        if self.reorganization_history:
            # Group by category
            files_by_category = {}
            for file_info in self.reorganization_history:
                category = file_info['category']
                if category not in files_by_category:
                    files_by_category[category] = []
                files_by_category[category].append(file_info)
            
            for category, files in files_by_category.items():
                content += f"### {category.replace('_', ' ').title()}\n\n"
                
                content += "| Original Location | New Location | Size |\n"
                content += "|-------------------|--------------|------|\n"
                
                for file_info in files:
                    size = self._format_size(file_info['size'])
                    content += f"| `{file_info['original_path']}` | `{file_info['new_path']}` | {size} |\n"
                
                content += "\n"
        else:
            content += "No file movements recorded.\n\n"
        
        # Link updates section
        if self.link_updates:
            content += "## Link Updates\n\n"
            content += "The following internal links were updated to reflect the new structure:\n\n"
            
            content += "| File | Old Link | New Link |\n"
            content += "|------|----------|----------|\n"
            
            for link_update in self.link_updates:
                content += f"| `{link_update['file']}` | `{link_update['old_link']}` | `{link_update['new_link']}` |\n"
            
            content += "\n"
        
        content += """## Benefits of Reorganization

1. **Improved Discoverability**: Related documentation is grouped together
2. **Better Navigation**: Clear hierarchy makes it easier to find information
3. **Consistent Structure**: Standardized organization across all documentation
4. **Easier Maintenance**: Logical grouping makes updates and maintenance simpler
5. **Better User Experience**: Users can quickly find the information they need

## Accessing Old Locations

If you have bookmarks or references to old documentation locations, use this mapping to find the new locations. All content has been preserved - only the organization has changed.

## Maintenance

- New documentation should be placed in the appropriate category directory
- Update the main README.md index when adding new major sections
- Keep the structure consistent with the established patterns
- Update cross-references when moving or renaming files

"""
        
        return content
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes == 0:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        
        return f"{size_bytes:.1f} GB"
    
    def validate_reorganization(self) -> Dict[str, List[str]]:
        """
        Validate the documentation reorganization.
        
        Returns:
            Dictionary of validation results
        """
        issues = {
            "missing_files": [],
            "broken_links": [],
            "empty_directories": []
        }
        
        # Check if moved files exist
        for file_info in self.reorganization_history:
            new_path = Path(file_info["new_path"])
            if not new_path.exists():
                issues["missing_files"].append(file_info["new_path"])
        
        # Check for empty directories
        for root, dirs, files in os.walk(self.docs_dir):
            root_path = Path(root)
            if not files and not dirs:
                issues["empty_directories"].append(str(root_path))
        
        # TODO: Add broken link detection
        
        return issues