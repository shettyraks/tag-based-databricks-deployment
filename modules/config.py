"""Configuration management module for deployment system."""

import os
import yaml
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class EnvironmentConfig:
    """Configuration for a single environment."""
    customer: str
    catalog: str
    schemas: List[str]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnvironmentConfig':
        """Create EnvironmentConfig from dictionary."""
        return cls(
            customer=data.get('customer', ''),
            catalog=data.get('catalog', ''),
            schemas=data.get('schemas', [])
        )


class ConfigManager:
    """Manages configuration for multiple environments."""
    
    def __init__(self, config_path: str = 'config/customer_input.yml'):
        """Initialize configuration manager.
        
        Args:
            config_path: Path to configuration YAML file
        """
        self.config_path = Path(config_path)
        self._config_data: Optional[Dict[str, Any]] = None
        self._environments: Optional[Dict[str, EnvironmentConfig]] = None
        
    def load(self) -> None:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            self._config_data = yaml.safe_load(f)
        
        # Parse environments
        self._environments = {}
        environments_data = self._config_data.get('environments', {})
        
        for env_name, env_data in environments_data.items():
            self._environments[env_name] = EnvironmentConfig.from_dict(env_data)
    
    def get_environment(self, environment: str) -> EnvironmentConfig:
        """Get configuration for a specific environment.
        
        Args:
            environment: Environment name (dev, sit, uat, prod)
            
        Returns:
            EnvironmentConfig for the specified environment
        """
        if self._environments is None:
            self.load()
        
        if environment not in self._environments:
            raise ValueError(f"Environment '{environment}' not found in config")
        
        return self._environments[environment]
    
    def get_all_environments(self) -> Dict[str, EnvironmentConfig]:
        """Get all environment configurations.
        
        Returns:
            Dictionary of environment name to EnvironmentConfig
        """
        if self._environments is None:
            self.load()
        
        return self._environments.copy()
    
    def validate(self, environment: Optional[str] = None) -> bool:
        """Validate configuration data.
        
        Args:
            environment: Optional environment name to validate. If None, validates all environments.
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        if self._environments is None:
            self.load()
        
        errors = []
        
        # If environment is specified, only validate that environment
        environments_to_check = {environment: self._environments[environment]} if environment else self._environments
        
        if environment and environment not in self._environments:
            raise ValueError(f"Environment '{environment}' not found in config")
        
        for env_name, env_config in environments_to_check.items():
            # Check for placeholder values
            if 'TBD' in env_config.customer or 'CHANGE_ME' in env_config.customer:
                errors.append(f"Environment '{env_name}' has placeholder customer value")
            
            if not env_config.catalog:
                errors.append(f"Environment '{env_name}' missing catalog")
            
            if not env_config.schemas:
                errors.append(f"Environment '{env_name}' missing schemas")
        
        if errors:
            raise ValueError(f"Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
        
        return True
    
    def get_sql_files_for_version(self, version: str, include_repeatable: bool = True) -> List[str]:
        """Get SQL files for a specific version using git history.
        
        This method automatically detects SQL files that exist at a specific git tag,
        eliminating the need to manually maintain version mappings.
        
        Args:
            version: Version tag (e.g., 'v1.0.0')
            include_repeatable: Whether to include repeatable migrations (R__*.sql)
        
        Returns:
            List of SQL file paths for the specified version
        """
        # First, try to get SQL files from git at the specific tag
        sql_files = self._get_sql_files_from_git_tag(version)
        
        if sql_files:
            print(f"✅ Found {len(sql_files)} SQL files for version {version} using git")
            return sorted(sql_files)
        
        # Fallback: if git tag doesn't exist or can't be accessed, use all files
        print(f"⚠️ Could not determine SQL files for version {version} from git. Deploying all SQL files.")
        return self._get_all_sql_files(include_repeatable)
    
    def _get_sql_files_from_git_tag(self, tag: str) -> List[str]:
        """Get SQL files that exist at a specific git tag.
        
        Args:
            tag: Git tag name
        
        Returns:
            List of SQL file paths that exist at the tag, or empty list if tag doesn't exist
        """
        sql_files = []
        
        try:
            # Check if tag exists
            result = subprocess.run(
                ['git', 'rev-parse', '--verify', f'{tag}^{{}}'],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                # Tag doesn't exist
                return []
            
            # Get all SQL files at this tag (git ls-tree doesn't support glob, so we filter manually)
            result = subprocess.run(
                ['git', 'ls-tree', '-r', '--name-only', tag],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0 and result.stdout.strip():
                all_files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
                # Filter for SQL files in sql_deployment directories
                sql_files = [
                    f for f in all_files 
                    if '/sql_deployment/' in f and f.endswith('.sql')
                ]
            
            # Remove duplicates
            sql_files = list(set(sql_files))
            
        except Exception as e:
            print(f"⚠️ Error getting SQL files from git tag {tag}: {e}")
            return []
        
        return sql_files
    
    def get_sql_files_between_tags(self, from_tag: Optional[str], to_tag: str, include_repeatable: bool = True) -> List[str]:
        """Get SQL files that were added or modified between two tags.
        
        Args:
            from_tag: Starting tag (None means from beginning)
            to_tag: Ending tag
            include_repeatable: Whether to include repeatable migrations
        
        Returns:
            List of SQL file paths changed between tags
        """
        sql_files = []
        
        try:
            if from_tag:
                # Get files added between two tags
                result = subprocess.run(
                    ['git', 'diff', '--name-only', '--diff-filter=A', f'{from_tag}..{to_tag}'],
                    capture_output=True,
                    text=True,
                    check=False
                )
            else:
                # Get all files up to the tag
                result = subprocess.run(
                    ['git', 'ls-tree', '-r', '--name-only', to_tag],
                    capture_output=True,
                    text=True,
                    check=False
                )
            
            if result.returncode == 0 and result.stdout.strip():
                all_files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
                # Filter for SQL files in sql_deployment directories
                sql_files = [
                    f for f in all_files 
                    if '/sql_deployment/' in f and f.endswith('.sql')
                ]
            
            # Filter repeatable migrations if needed
            if not include_repeatable:
                sql_files = [f for f in sql_files if not Path(f).name.startswith('R__')]
            
        except Exception as e:
            print(f"⚠️ Error getting SQL files between tags: {e}")
            return []
        
        return sorted(list(set(sql_files)))
    
    def _get_all_sql_files(self, include_repeatable: bool = True) -> List[str]:
        """Get all SQL files in the repository.
        
        Args:
            include_repeatable: Whether to include repeatable migrations
        
        Returns:
            List of all SQL file paths
        """
        sql_files = []
        sql_dirs = Path('src').rglob('sql_deployment')
        
        for sql_dir in sql_dirs:
            for sql_file in sql_dir.glob('*.sql'):
                if include_repeatable or not sql_file.name.startswith('R__'):
                    sql_files.append(str(sql_file))
        
        return sorted(sql_files)
    
    def _get_repeatable_sql_files(self) -> List[str]:
        """Get all repeatable SQL migration files (R__*.sql).
        
        Returns:
            List of repeatable SQL file paths
        """
        repeatable_files = []
        sql_dirs = Path('src').rglob('sql_deployment')
        
        for sql_dir in sql_dirs:
            for sql_file in sql_dir.glob('R__*.sql'):
                repeatable_files.append(str(sql_file))
        
        return sorted(repeatable_files)


class DeploymentConfig:
    """Configuration for a deployment run."""
    
    def __init__(self, environment: str):
        """Initialize deployment configuration.
        
        Args:
            environment: Environment name (dev, sit, uat, prod)
        """
        self.environment = environment
        self.config_manager = ConfigManager()
        self.env_config = self.config_manager.get_environment(environment)
        
        # Load Databricks credentials from environment
        self.databricks_host = os.environ.get('DATABRICKS_HOST')
        self.databricks_token = os.environ.get('DATABRICKS_TOKEN')
        
        # Service Principal credentials (alternative to token)
        self.service_principal_client_id = os.environ.get(f'SERVICE_PRINCIPAL_CLIENT_ID_{environment.upper()}')
        self.service_principal_client_secret = os.environ.get(f'SERVICE_PRINCIPAL_CLIENT_SECRET_{environment.upper()}')
        self.service_principal_tenant_id = os.environ.get(f'SERVICE_PRINCIPAL_TENANT_ID_{environment.upper()}')
        
        # Determine authentication method
        self.auth_method = self._determine_auth_method()
        
        # Load SQL connection credentials (can be token or service principal)
        self.http_path = os.environ.get(f'HTTP_PATH_{environment.upper()}')
        # SQL_USER defaults to 'token' if not set or empty
        sql_user_env = os.environ.get(f'SQL_USER_{environment.upper()}')
        self.sql_user = sql_user_env if sql_user_env else 'token'
        # SQL_PASSWORD defaults to DATABRICKS_TOKEN if not set or empty
        sql_password_env = os.environ.get(f'SQL_PASSWORD_{environment.upper()}')
        self.sql_password = sql_password_env if sql_password_env else self.databricks_token
    
    def _determine_auth_method(self) -> str:
        """Determine which authentication method to use.
        
        Returns:
            'service_principal' or 'token'
        """
        has_service_principal = all([
            self.service_principal_client_id,
            self.service_principal_client_secret,
            self.service_principal_tenant_id
        ])
        
        if has_service_principal:
            return 'service_principal'
        elif self.databricks_token:
            return 'token'
        else:
            return 'token'  # Default to token
    
    def get_jdbc_url(self) -> str:
        """Get JDBC URL with support for both token and service principal auth.
        
        Returns:
            JDBC URL string
        """
        if not all([self.databricks_host, self.http_path]):
            raise ValueError("Missing required Databricks credentials")
        
        # Build base JDBC URL
        jdbc_url = (f"jdbc:databricks://{self.databricks_host}:443;"
                   f"transportMode=http;ssl=1;"
                   f"httpPath={self.http_path};"
                   f"ConnCatalog={self.env_config.catalog}")
        
        # Add authentication parameters based on method
        if self.auth_method == 'service_principal':
            # Service Principal authentication
            if not all([self.service_principal_client_id, self.service_principal_client_secret, 
                       self.service_principal_tenant_id]):
                raise ValueError("Missing service principal credentials")
            
            jdbc_url += (f"AuthMech=11;"
                        f"UID={self.service_principal_client_id};"
                        f"PWD={self.service_principal_client_secret};"
                        f"TenantId={self.service_principal_tenant_id}")
        else:
            # Token authentication (default)
            if not self.sql_user or not self.sql_password:
                raise ValueError("Missing SQL credentials for token authentication")
            
            jdbc_url += f"AuthMech=3;UID={self.sql_user};PWD={self.sql_password}"
        
        return jdbc_url
    
    def get_schemas_str(self) -> str:
        """Get comma-separated schemas string."""
        return ','.join(self.env_config.schemas)
    
    def validate(self) -> bool:
        """Validate deployment configuration.
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If required credentials are missing
        """
        errors = []
        env_suffix = self.environment.upper()
        
        if not self.databricks_host:
            errors.append("DATABRICKS_HOST not set")
        
        if not self.http_path:
            errors.append(f"HTTP_PATH_{env_suffix} not set")
        
        # Validate based on authentication method
        if self.auth_method == 'service_principal':
            # Service Principal authentication
            if not self.service_principal_client_id:
                errors.append(f"SERVICE_PRINCIPAL_CLIENT_ID_{env_suffix} not set")
            if not self.service_principal_client_secret:
                errors.append(f"SERVICE_PRINCIPAL_CLIENT_SECRET_{env_suffix} not set")
            if not self.service_principal_tenant_id:
                errors.append(f"SERVICE_PRINCIPAL_TENANT_ID_{env_suffix} not set")
            
            # For DABs, we need either token or service principal for Databricks CLI
            if not self.databricks_token:
                errors.append("DATABRICKS_TOKEN not set (required for CLI even with service principal)")
        else:
            # Token authentication
            if not self.databricks_token:
                errors.append("DATABRICKS_TOKEN not set")
            # SQL_USER defaults to 'token', so we only need to check SQL_PASSWORD
            # SQL_PASSWORD defaults to DATABRICKS_TOKEN, so if token is set, password will be set
            if not self.sql_password:
                errors.append(f"SQL_PASSWORD_{env_suffix} not set (defaults to DATABRICKS_TOKEN if not provided)")
        
        if errors:
            error_msg = f"Missing required credentials for {self.environment} environment:\n" + "\n".join(f"  - {e}" for e in errors)
            error_msg += f"\n\nPlease configure these secrets in GitHub repository settings:\n"
            error_msg += f"Settings → Secrets and variables → Actions → Environment secrets (for '{self.environment}' environment)"
            raise ValueError(error_msg)
        
        return True
    
    def get_databricks_config(self) -> Dict[str, str]:
        """Get Databricks CLI configuration based on auth method.
        
        Returns:
            Dictionary of configuration environment variables
        """
        config = {
            'DATABRICKS_HOST': self.databricks_host,
        }
        
        if self.auth_method == 'service_principal':
            config['DATABRICKS_AUTH_TYPE'] = 'azure-cli'
            # Note: Service principal auth for CLI typically requires az login first
            # or we can set client ID and secret for direct auth
            if self.service_principal_client_id and self.service_principal_client_secret:
                config['ARM_CLIENT_ID'] = self.service_principal_client_id
                config['ARM_CLIENT_SECRET'] = self.service_principal_client_secret
                config['ARM_TENANT_ID'] = self.service_principal_tenant_id
        else:
            config['DATABRICKS_TOKEN'] = self.databricks_token
        
        return config

