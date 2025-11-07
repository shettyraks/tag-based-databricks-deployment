#!/usr/bin/env python3
"""
Main deployment script for synapse-to-databricks migration.
Orchestrates the complete deployment process with modular architecture.
"""

import sys
import argparse
import subprocess
from pathlib import Path
from typing import Optional

from modules.deployment_orchestrator import DeploymentOrchestrator


def get_current_git_tag() -> Optional[str]:
    """Get the current git tag if HEAD is on a tag.
    
    Returns:
        Tag name if HEAD is on a tag, None otherwise
    """
    try:
        result = subprocess.run(
            ['git', 'describe', '--exact-match', '--tags', 'HEAD'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_latest_tag() -> Optional[str]:
    """Get the latest git tag.
    
    Returns:
        Latest tag name or None
    """
    try:
        result = subprocess.run(
            ['git', 'describe', '--tags', '--abbrev=0'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def main():
    """Main deployment entry point."""
    parser = argparse.ArgumentParser(
        description='Deploy synapse-to-databricks migration',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy to development environment
  python deploy.py --environment dev

  # Deploy to production with backup
  python deploy.py --environment prod

  # Deploy to SIT without validation
  python deploy.py --environment sit --skip-validation

  # Deploy with debug output
  python deploy.py --environment dev --debug
        """
    )
    
    parser.add_argument(
        '--environment',
        required=True,
        choices=['dev', 'sit', 'uat', 'prod'],
        help='Target environment for deployment'
    )
    
    parser.add_argument(
        '--skip-backup',
        action='store_true',
        help='Skip backup creation before deployment'
    )
    
    parser.add_argument(
        '--skip-migrations',
        action='store_true',
        help='Skip SQL migrations'
    )
    
    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip post-deployment validation'
    )
    
    parser.add_argument(
        '--skip-smoke-tests',
        action='store_true',
        help='Skip smoke tests'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug output'
    )
    
    parser.add_argument(
        '--version',
        type=str,
        default=None,
        help='Version tag to deploy (e.g., v1.0.0). If not specified, uses current git tag or latest tag.'
    )
    
    args = parser.parse_args()
    
    # Determine version to use
    version = args.version
    if not version:
        version = get_current_git_tag()
    if not version:
        version = get_latest_tag()
    if version:
        print(f"📦 Deploying SQL files for version: {version}")
    else:
        print("⚠️ No version specified and no git tag found. Deploying all SQL files.")
    
    try:
        # Create orchestrator
        orchestrator = DeploymentOrchestrator(args.environment, version=version)
        
        # Run deployment
        success = orchestrator.deploy(
            run_backup=not args.skip_backup,
            skip_migrations=args.skip_migrations,
            skip_validation=args.skip_validation,
            skip_smoke_tests=args.skip_smoke_tests,
            debug=args.debug
        )
        
        if success:
            print("\n✅ Deployment completed successfully")
            sys.exit(0)
        else:
            print("\n❌ Deployment failed")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️ Deployment interrupted by user")
        sys.exit(130)
        
    except Exception as e:
        print(f"\n❌ Deployment failed with error: {str(e)}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

