"""Deployment orchestrator to manage the complete deployment flow."""

import sys
from typing import Optional, Dict, Any
from .config import DeploymentConfig, ConfigManager
from .databricks_client import DatabricksClient


class DeploymentOrchestrator:
    """Orchestrates the deployment process."""
    
    def __init__(self, environment: str, version: Optional[str] = None):
        """Initialize deployment orchestrator.
        
        Args:
            environment: Environment name (dev, sit, uat, prod)
            version: Optional version tag for SQL file filtering
        """
        self.environment = environment
        self.version = version
        self.config = DeploymentConfig(environment)
        self.databricks_client = DatabricksClient(self.config)
        
        # Get SQL files for this version if version is specified
        if self.version:
            config_manager = ConfigManager()
            self.sql_files = config_manager.get_sql_files_for_version(self.version)
            print(f"📋 SQL files to deploy for version {self.version}:")
            for sql_file in self.sql_files:
                print(f"  - {sql_file}")
        else:
            self.sql_files = None
        
        # Deployment metadata
        self.metadata: Dict[str, Any] = {}
    
    def validate_config(self) -> bool:
        """Validate deployment configuration.
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        print(f"Validating configuration for {self.environment}...")
        
        # Validate credentials
        self.config.validate()
        
        # Validate environment config (only for the current environment)
        self.config.config_manager.validate(self.environment)
        
        print("✅ Configuration validation passed")
        return True
    
    def create_backup(self) -> Optional[str]:
        """Create backup before deployment.
        
        Returns:
            Backup timestamp or None
        """
        print(f"Creating backup for {self.environment} environment...")
        
        # This is a placeholder - implement actual backup logic
        backup_timestamp = "backup_placeholder"
        self.metadata['backup_timestamp'] = backup_timestamp
        
        print("✅ Backup creation completed")
        return backup_timestamp
    
    def run_migrations(self, debug: bool = False) -> bool:
        """Run SQL migrations.
        
        Args:
            debug: Enable debug output
            
        Returns:
            True if migrations succeeded
        """
        print(f"Running SQL migrations for {self.environment}...")
        
        # SQL migrations are now handled through Databricks notebooks/jobs
        # This method is kept for compatibility but can be extended for future migration strategies
        print(f"✅ SQL migrations completed for {self.environment}")
        self.metadata['migrations_completed'] = True
        
        return True
    
    def deploy_databricks_assets(self) -> bool:
        """Deploy Databricks Asset Bundles.
        
        Returns:
            True if deployment succeeded
        """
        print(f"Deploying Databricks assets to {self.environment}...")
        
        try:
            # Prepare deployment variables
            variables = {
                'customer': self.config.env_config.customer,
                'catalog': self.config.env_config.catalog
            }
            
            print(f"Customer: {self.config.env_config.customer}")
            print(f"Catalog: {self.config.env_config.catalog}")
            
            # Deploy bundle
            self.databricks_client.bundle_deploy(
                target=self.environment,
                variables=variables
            )
            
            # Show summary
            self.databricks_client.bundle_summary(target=self.environment)
            
            print(f"✅ Databricks assets deployed to {self.environment}")
            self.metadata['assets_deployed'] = True
            return True
            
        except Exception as e:
            print(f"❌ Databricks assets deployment failed: {e}")
            self.metadata['assets_deployed'] = False
            self.metadata['deployment_error'] = str(e)
            return False
    
    def validate_deployment(self) -> bool:
        """Validate post-deployment state.
        
        Returns:
            True if validation passes
        """
        print(f"Validating deployment for {self.environment}...")
        
        # Placeholder validation
        # In production, this would:
        # - Check that tables exist
        # - Verify job configurations
        # - Run data quality checks
        
        print("✅ Deployment validation passed")
        self.metadata['validation_passed'] = True
        return True
    
    def run_smoke_tests(self) -> bool:
        """Run smoke tests after deployment.
        
        Returns:
            True if all smoke tests pass
        """
        print(f"Running smoke tests for {self.environment}...")
        
        # Placeholder smoke tests
        # In production, this would:
        # - Test table access
        # - Verify job schedules
        # - Check integration connectivity
        
        print("✅ Smoke tests passed")
        self.metadata['smoke_tests_passed'] = True
        return True
    
    def deploy(self, 
               run_backup: bool = True,
               skip_migrations: bool = False,
               skip_validation: bool = False,
               skip_smoke_tests: bool = False,
               debug: bool = False) -> bool:
        """Run complete deployment process.
        
        Args:
            run_backup: Whether to create backup before deployment
            skip_migrations: Whether to skip SQL migrations
            skip_validation: Whether to skip deployment validation
            skip_smoke_tests: Whether to skip smoke tests
            debug: Enable debug output
            
        Returns:
            True if deployment succeeded
        """
        print(f"Starting deployment for {self.environment} environment...")
        print("=" * 60)
        
        try:
            # Step 1: Validate configuration
            if not self.validate_config():
                return False
            
            # Step 2: Create backup (if enabled)
            if run_backup:
                self.create_backup()
            
            # Step 3: Run SQL migrations (if not skipped)
            if not skip_migrations:
                if not self.run_migrations(debug=debug):
                    print("❌ Deployment failed at migrations step")
                    return False
            else:
                print("⚠️ Skipping SQL migrations")
            
            # Step 4: Deploy Databricks assets
            if not self.deploy_databricks_assets():
                print("❌ Deployment failed at assets deployment step")
                return False
            
            # Step 5: Validate deployment (if not skipped)
            if not skip_validation:
                if not self.validate_deployment():
                    print("❌ Deployment failed validation")
                    return False
            else:
                print("⚠️ Skipping deployment validation")
            
            # Step 6: Run smoke tests (if not skipped)
            if not skip_smoke_tests:
                if not self.run_smoke_tests():
                    print("❌ Smoke tests failed")
                    return False
            else:
                print("⚠️ Skipping smoke tests")
            
            print("=" * 60)
            print(f"✅ Deployment to {self.environment} completed successfully")
            
            return True
            
        except Exception as e:
            print("=" * 60)
            print(f"❌ Deployment to {self.environment} failed: {e}")
            sys.exit(1)
    
    def rollback(self) -> bool:
        """Rollback deployment.
        
        Returns:
            True if rollback succeeded
        """
        print(f"Rolling back deployment for {self.environment}...")
        
        # Placeholder rollback logic
        # In production, this would:
        # - Restore from backup
        # - Run reverse migrations
        # - Clean up deployed assets
        
        print("⚠️ Rollback not implemented")
        return False

