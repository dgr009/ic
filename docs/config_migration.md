# Configuration Directory Migration Guide

## Overview

IC has migrated from using `config/` directory to `.ic/config/` directory for better organization and to follow modern CLI tool conventions. This change provides:

- **Better Organization**: Configuration files are now in a dedicated `.ic/` directory
- **Reduced Clutter**: Project root directory is cleaner
- **Standard Convention**: Follows the pattern used by other CLI tools
- **Backward Compatibility**: Legacy `config/` paths are still supported

## Migration Path

### Automatic Migration

IC automatically handles the migration for you:

1. **New Installations**: Use `.ic/config/` by default
2. **Existing Installations**: Continue to work with `config/` directory
3. **Gradual Migration**: You can migrate at your own pace

### Manual Migration Steps

If you want to migrate to the new structure:

```bash
# 1. Create new configuration directory
mkdir -p .ic/config

# 2. Move existing configuration files
mv config/default.yaml .ic/config/default.yaml
mv config/secrets.yaml .ic/config/secrets.yaml
mv config/secrets.yaml.example .ic/config/secrets.yaml.example

# 3. Update .gitignore (if needed)
# Remove: config/secrets.yaml
# Add: .ic/config/secrets.yaml

# 4. Verify the migration
ic config show
```

## Configuration File Locations

### New Structure (Preferred)
```
.ic/
├── config/
│   ├── default.yaml          # Main configuration
│   ├── secrets.yaml          # Sensitive data (gitignored)
│   └── secrets.yaml.example  # Example template
└── ...
```

### Legacy Structure (Still Supported)
```
config/
├── default.yaml
├── secrets.yaml
└── secrets.yaml.example
```

## Search Priority

IC searches for configuration files in this order:

1. `.ic/config/default.yaml` (preferred)
2. `config/default.yaml` (legacy)
3. `~/.ic/config/default.yaml` (user-specific)
4. `/etc/ic/config.yaml` (system-wide)

For secrets:
1. `.ic/config/secrets.yaml` (preferred)
2. `config/secrets.yaml` (legacy)
3. Environment variables

## Backward Compatibility

- **Existing Projects**: Continue to work without changes
- **Mixed Environments**: Both directory structures can coexist
- **Gradual Migration**: Migrate projects individually as needed
- **No Breaking Changes**: All existing functionality remains intact

## Benefits of Migration

### For New Projects
- Cleaner project root directory
- Standard CLI tool convention
- Better organization of IC-related files

### For Existing Projects
- Optional migration - no pressure to change
- Improved organization when you're ready
- Future-proof configuration structure

## Troubleshooting

### Configuration Not Found
If IC can't find your configuration:

```bash
# Check current configuration sources
ic config show --sources

# Verify file locations
ls -la .ic/config/
ls -la config/

# Test configuration loading
ic config validate
```

### Permission Issues
Ensure proper file permissions:

```bash
# New structure
chmod 700 .ic/config/
chmod 600 .ic/config/secrets.yaml
chmod 644 .ic/config/default.yaml

# Legacy structure (if still using)
chmod 600 config/secrets.yaml
chmod 644 config/default.yaml
```

### Git Configuration
Update your `.gitignore`:

```gitignore
# New structure
.ic/config/secrets.yaml

# Legacy structure (keep if still using)
config/secrets.yaml

# Environment files
.env
.env.local
```

## FAQ

**Q: Do I need to migrate immediately?**
A: No, the legacy `config/` directory continues to work. Migrate when convenient.

**Q: Can I use both directory structures?**
A: Yes, but IC will prefer the new `.ic/config/` structure when both exist.

**Q: What happens to my existing configuration?**
A: Nothing changes automatically. Your existing configuration continues to work.

**Q: How do I know which structure I'm using?**
A: Run `ic config show --sources` to see which files are being loaded.

**Q: Can I revert the migration?**
A: Yes, simply move the files back to the `config/` directory.

## Support

If you encounter issues during migration:

1. Check the troubleshooting section above
2. Run `ic config validate` for detailed diagnostics
3. Review the configuration documentation
4. Check file permissions and paths
5. Verify your `.gitignore` settings

The migration is designed to be safe and reversible. Take your time and migrate when it's convenient for your workflow.