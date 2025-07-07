# GitHub Actions Setup for PyPI Deployment

This repository uses GitHub Actions with PyPI Trusted Publishing to automatically deploy to PyPI when the version in `pyproject.toml` is updated.

## Workflow

### `deploy-pypi.yml` - Trusted Publishing
- **Trigger**: Push to `main` or `master` branch
- **Functionality**: 
  - Checks if the current version in `pyproject.toml` exists on PyPI
  - If not, builds and deploys the package using trusted publishing
  - Creates a Git tag and GitHub release
- **Security**: Uses PyPI's trusted publishing (no API tokens required)

## How It Works

1. **Version Detection**: The workflow reads the version from `pyproject.toml`
2. **PyPI Check**: It checks if this version already exists on PyPI
3. **Conditional Deployment**: Only deploys if the version is new
4. **Release Creation**: Automatically creates a Git tag and GitHub release

## Example Workflow

1. Update version in `pyproject.toml`:
   ```toml
   version = "0.2.0"  # Changed from 0.1.0
   ```

2. Commit and push:
   ```bash
   git add pyproject.toml
   git commit -m "Bump version to 0.2.0"
   git push origin main
   ```

3. The GitHub Action will:
   - Detect the new version
   - Build the package
   - Deploy to PyPI
   - Create tag `v0.2.0`
   - Create a GitHub release

## Troubleshooting

- **Trusted publishing not configured**: Make sure you've added the GitHub repository as a trusted publisher on PyPI
- **Version already exists**: The workflow skips deployment if the version already exists on PyPI
- **Build fails**: Check that your `pyproject.toml` and package structure are correct
- **Permission denied**: Ensure the workflow name matches exactly what you configured on PyPI

## Security Benefits

- **No API tokens**: Trusted publishing eliminates the need to store sensitive API tokens
- **Short-lived tokens**: PyPI generates temporary tokens for each deployment
- **Repository-specific**: Tokens are tied to your specific repository and workflow
- **Audit trail**: Better logging and security monitoring
