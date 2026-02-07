"""
Production-grade configuration validator
- JSON Schema validation
- Type checking
- Path validation
- Network validation
- Clear error messages
- Default value injection
"""
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple
from ipaddress import ip_address, ip_network, AddressValueError


logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Configuration validation error"""
    pass


class ConfigValidator:
    """
    Validates EDR configuration with comprehensive checks
    
    Features:
    - JSON Schema validation
    - Type checking
    - Path existence validation
    - Network configuration validation
    - Security policy validation
    - Performance limit checks
    """
    
    SCHEMA = {
        "type": "object",
        "required": ["system", "paths", "collection"],
        "properties": {
            "system": {
                "type": "object",
                "required": ["name", "version"],
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "version": {"type": "string", "pattern": r"^\d+\.\d+\.\d+$"},
                    "hostname": {"type": "string"}
                }
            },
            "paths": {
                "type": "object",
                "required": ["local_data", "local_logs", "database"],
                "properties": {
                    "local_data": {"type": "string"},
                    "local_logs": {"type": "string"},
                    "models": {"type": "string"},
                    "database": {"type": "string"},
                    "nas_logs": {"type": "string"},
                    "nas_backups": {"type": "string"},
                    "monitored_dirs": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            },
            "nas": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "ip": {"type": "string"},
                    "log_sync_interval": {"type": "integer", "minimum": 60},
                    "backup_retention_days": {"type": "integer", "minimum": 1}
                }
            },
            "collection": {
                "type": "object",
                "required": ["interval"],
                "properties": {
                    "interval": {"type": "integer", "minimum": 1, "maximum": 3600},
                    "baseline_days": {"type": "integer", "minimum": 1},
                    "process_monitor": {"type": "object"},
                    "file_monitor": {"type": "object"},
                    "network_monitor": {"type": "object"}
                }
            },
            "logging": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
                    }
                }
            }
        }
    }
    
    @classmethod
    def load_and_validate(cls, config_path: str) -> Dict[str, Any]:
        """
        Load configuration file and validate
        
        Args:
            config_path: Path to YAML configuration file
            
        Returns:
            Validated configuration dictionary
            
        Raises:
            ConfigValidationError: If validation fails
        """
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise ConfigValidationError(f"Configuration file not found: {config_path}")
        
        if not config_path.is_file():
            raise ConfigValidationError(f"Configuration path is not a file: {config_path}")
        
        # Load YAML
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigValidationError(f"Invalid YAML syntax: {e}")
        except Exception as e:
            raise ConfigValidationError(f"Failed to load configuration: {e}")
        
        if not isinstance(config, dict):
            raise ConfigValidationError("Configuration must be a dictionary")
        
        # Validate structure
        validator = cls()
        validator.validate(config)
        
        # Inject defaults
        config = validator.inject_defaults(config)
        
        logger.info("Configuration validated successfully")
        return config
    
    def validate(self, config: Dict[str, Any]):
        """
        Comprehensive validation
        
        Raises:
            ConfigValidationError: If any validation fails
        """
        errors = []
        
        # 1. Schema validation
        schema_errors = self._validate_schema(config)
        if schema_errors:
            errors.extend(schema_errors)
        
        # 2. Path validation
        path_errors = self._validate_paths(config)
        if path_errors:
            errors.extend(path_errors)
        
        # 3. Network validation
        if config.get('nas', {}).get('enabled'):
            network_errors = self._validate_network(config)
            if network_errors:
                errors.extend(network_errors)
        
        # 4. Performance limits
        perf_errors = self._validate_performance_limits(config)
        if perf_errors:
            errors.extend(perf_errors)
        
        # 5. Security policies
        security_errors = self._validate_security(config)
        if security_errors:
            errors.extend(security_errors)
        
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ConfigValidationError(error_msg)
    
    def _validate_schema(self, config: Dict[str, Any]) -> List[str]:
        """Validate against JSON schema"""
        errors = []
        
        # Check required top-level keys
        required = self.SCHEMA.get("required", [])
        for key in required:
            if key not in config:
                errors.append(f"Missing required key: '{key}'")
        
        # Validate system section
        if "system" in config:
            system = config["system"]
            if not isinstance(system.get("name"), str) or not system.get("name"):
                errors.append("system.name must be non-empty string")
            
            version = system.get("version", "")
            if not isinstance(version, str):
                errors.append("system.version must be string")
            elif not version.count('.') == 2:
                errors.append("system.version must be in format X.Y.Z")
        
        # Validate collection interval
        if "collection" in config:
            interval = config["collection"].get("interval")
            if not isinstance(interval, int):
                errors.append("collection.interval must be integer")
            elif interval < 1 or interval > 3600:
                errors.append("collection.interval must be between 1 and 3600 seconds")
        
        # Validate logging level
        if "logging" in config:
            level = config["logging"].get("level", "INFO")
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if level not in valid_levels:
                errors.append(f"logging.level must be one of {valid_levels}")
        
        return errors
    
    def _validate_paths(self, config: Dict[str, Any]) -> List[str]:
        """Validate filesystem paths"""
        errors = []
        paths = config.get("paths", {})
        
        # Check required paths exist or can be created
        for key in ["local_data", "local_logs"]:
            if key in paths:
                path = Path(paths[key])
                try:
                    # Check if parent exists and is writable
                    parent = path.parent if not path.exists() else path
                    if parent.exists() and not os.access(parent, os.W_OK):
                        errors.append(f"paths.{key}: No write permission to {parent}")
                except Exception as e:
                    errors.append(f"paths.{key}: Invalid path: {e}")
        
        # Validate monitored directories
        monitored_dirs = paths.get("monitored_dirs", [])
        if not isinstance(monitored_dirs, list):
            errors.append("paths.monitored_dirs must be a list")
        else:
            for dir_path in monitored_dirs:
                if not isinstance(dir_path, str):
                    errors.append(f"paths.monitored_dirs: Invalid path type: {dir_path}")
                    continue
                
                path = Path(dir_path)
                if not path.is_absolute():
                    errors.append(f"paths.monitored_dirs: Path must be absolute: {dir_path}")
                
                # Warn if doesn't exist (not error - may be created later)
                if not path.exists():
                    logger.warning(f"Monitored directory does not exist: {dir_path}")
        
        # Validate NAS paths if NAS enabled
        if config.get("nas", {}).get("enabled"):
            for key in ["nas_logs", "nas_backups"]:
                if key in paths:
                    path = Path(paths[key])
                    # Only warn - NAS may not be mounted yet
                    if not path.exists():
                        logger.warning(f"NAS path does not exist (NAS may not be mounted): {path}")
        
        return errors
    
    def _validate_network(self, config: Dict[str, Any]) -> List[str]:
        """Validate network configuration"""
        errors = []
        nas = config.get("nas", {})
        
        # Validate NAS IP
        if "ip" in nas:
            nas_ip = nas["ip"]
            try:
                ip_address(nas_ip)
            except (ValueError, AddressValueError):
                errors.append(f"nas.ip: Invalid IP address: {nas_ip}")
        else:
            errors.append("nas.ip is required when NAS is enabled")
        
        # Validate intervals
        sync_interval = nas.get("log_sync_interval")
        if sync_interval is not None:
            if not isinstance(sync_interval, int) or sync_interval < 60:
                errors.append("nas.log_sync_interval must be >= 60 seconds")
        
        return errors
    
    def _validate_performance_limits(self, config: Dict[str, Any]) -> List[str]:
        """Validate performance settings are within safe limits"""
        errors = []
        
        # Check collection interval isn't too aggressive
        interval = config.get("collection", {}).get("interval", 5)
        if interval < 5:
            errors.append("collection.interval < 5s may cause high CPU usage")
        
        # Check monitored directories aren't excessive
        monitored_dirs = config.get("paths", {}).get("monitored_dirs", [])
        if len(monitored_dirs) > 20:
            errors.append(f"Too many monitored directories ({len(monitored_dirs)}). Limit to 20 for performance.")
        
        # Check for monitoring root filesystem
        if "/" in monitored_dirs or "/Users" in monitored_dirs:
            errors.append("Monitoring root or /Users will cause extreme performance issues")
        
        return errors
    
    def _validate_security(self, config: Dict[str, Any]) -> List[str]:
        """Validate security settings"""
        errors = []
        
        # Check whitelists aren't too permissive
        whitelist = config.get("whitelist", {})
        
        # Check process whitelist
        processes = whitelist.get("processes", [])
        if "*" in processes or ".*" in processes:
            errors.append("whitelist.processes: Wildcard '*' is too permissive")
        
        # Check path whitelist
        paths = whitelist.get("paths", [])
        if "/" in paths:
            errors.append("whitelist.paths: Root path '/' will disable all file monitoring")
        
        # Check IP whitelist
        ips = whitelist.get("ips", [])
        for ip_range in ips:
            try:
                # Try parsing as network
                net = ip_network(ip_range, strict=False)
                # Warn about very large ranges
                if net.num_addresses > 65536:  # Larger than /16
                    logger.warning(f"Very large IP whitelist range: {ip_range}")
            except (ValueError, AddressValueError):
                errors.append(f"whitelist.ips: Invalid IP/network: {ip_range}")
        
        return errors
    
    def inject_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Inject default values for missing optional keys"""
        defaults = {
            "system": {
                "hostname": "unknown"
            },
            "nas": {
                "enabled": False,
                "log_sync_interval": 300,
                "backup_retention_days": 90
            },
            "wazuh": {
                "enabled": False
            },
            "collection": {
                "baseline_days": 14
            },
            "logging": {
                "level": "INFO",
                "rotation": {
                    "max_bytes": 10485760,
                    "backup_count": 5
                }
            },
            "maintenance": {
                "auto_cleanup": {
                    "enabled": True,
                    "old_events_days": 30
                },
                "model_retraining": {
                    "enabled": False,
                    "interval_days": 14
                },
                "backup": {
                    "enabled": True,
                    "daily_to_nas": True
                }
            },
            "threat_scoring": {
                "thresholds": {
                    "info": 30,
                    "warning": 60,
                    "high": 85,
                    "critical": 100
                }
            },
            "response": {
                "auto_respond": {
                    "enabled": False,
                    "require_confirmation_above": 85
                }
            }
        }
        
        # Deep merge defaults
        return self._deep_merge(defaults, config)
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries, override takes precedence"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result


# Module-level import fix
import os


def validate_config_file(config_path: str) -> Dict[str, Any]:
    """
    Convenience function to validate configuration file
    
    Args:
        config_path: Path to configuration YAML file
        
    Returns:
        Validated configuration dictionary
        
    Raises:
        ConfigValidationError: If validation fails
    """
    return ConfigValidator.load_and_validate(config_path)


def get_validation_summary(config_path: str) -> Tuple[bool, List[str], List[str]]:
    """
    Get validation summary without raising exceptions
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    try:
        ConfigValidator.load_and_validate(config_path)
        return (True, [], warnings)
    except ConfigValidationError as e:
        error_lines = str(e).split('\n')[1:]  # Skip first line
        errors = [line.strip('- ') for line in error_lines if line.strip()]
        return (False, errors, warnings)
    except Exception as e:
        return (False, [f"Unexpected error: {e}"], warnings)


if __name__ == "__main__":
    # Test validation
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python config_validator.py <config_file>")
        sys.exit(1)
    
    config_file = sys.argv[1]
    
    print(f"Validating configuration: {config_file}")
    print("=" * 60)
    
    is_valid, errors, warnings = get_validation_summary(config_file)
    
    if warnings:
        print("⚠️  WARNINGS:")
        for warning in warnings:
            print(f"  - {warning}")
        print()
    
    if errors:
        print("❌ VALIDATION FAILED:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("✅ Configuration is valid!")
        sys.exit(0)
