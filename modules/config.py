"""Configuration management module for deployment system."""

import os
import yaml
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
    
    def validate(self) -> bool:
        """Validate configuration data.
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        if self._environments is None:
            self.load()
        
        errors = []
        
        for env_name, env_config in self._environments.items():
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
        # SQL_USER defaults to 'token' if not set
        self.sql_user = os.environ.get(f'SQL_USER_{environment.upper()}', 'token')
        # SQL_PASSWORD defaults to DATABRICKS_TOKEN if not set
        self.sql_password = os.environ.get(f'SQL_PASSWORD_{environment.upper()}', self.databricks_token)
    
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

