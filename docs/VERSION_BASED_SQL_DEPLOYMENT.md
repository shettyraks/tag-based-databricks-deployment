# Version-Based SQL File Deployment

This feature automatically deploys only SQL files that exist at a specific git tag/version, eliminating the need for manual version mapping.

## How It Works

When you deploy with a version tag, the system:
1. Checks if the git tag exists
2. Lists all SQL files that exist at that tag point in git history
3. Deploys only those SQL files

This means:
- **New versions automatically work** - Just create a new git tag and deploy
- **No manual maintenance** - No need to update configuration files for each version
- **Accurate versioning** - Files are determined by what actually exists in git at that tag

## Usage

### Automatic Version Detection

```bash
# Deploy using current git tag (if HEAD is on a tag)
python deploy.py --environment dev

# Deploy using latest git tag
python deploy.py --environment dev
```

### Manual Version Specification

```bash
# Deploy specific version
python deploy.py --environment dev --version v1.0.0

# Deploy version v1.0.2
python deploy.py --environment dev --version v1.0.2
```

### Deploy All SQL Files (No Version Filtering)

```bash
# If no version is found and none specified, all SQL files are deployed
python deploy.py --environment dev
```

## Version Detection Priority

1. `--version` command line argument (highest priority)
2. Current git tag (if HEAD is on a tag)
3. Latest git tag
4. All SQL files (if no version found)

## Example Workflow

1. **Create SQL files** for your feature
2. **Commit and push** your changes
3. **Create git tag**: `git tag v1.0.3 -m "Add new SQL migrations"`
4. **Deploy**: `python deploy.py --environment dev --version v1.0.3`
5. Only SQL files that exist at tag `v1.0.3` will be deployed

## How New Versions Work

When you create a new version tag:

1. **Create the tag**: `git tag v1.0.3`
2. **Push the tag**: `git push origin v1.0.3`
3. **Deploy**: `python deploy.py --environment dev --version v1.0.3`

The system automatically detects all SQL files that exist at that tag - **no configuration needed!**

## Notes

- **Repeatable migrations** (`R__*.sql`) are always included if they exist at the tag
- **Versioned migrations** (`V{number}__*.sql`) are included if they exist at the tag
- If a tag doesn't exist, all SQL files are deployed as a fallback
- The system uses `git ls-tree` to determine which files exist at a specific tag

