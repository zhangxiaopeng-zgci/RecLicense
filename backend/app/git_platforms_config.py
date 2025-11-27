"""
Git Platforms Configuration for RecLicense
Supports public and private Git platform deployments
"""

import os
import yaml
import logging

# Default built-in platforms
DEFAULT_PLATFORMS = {
    'github': {
        'name': 'GitHub',
        'api_url': 'https://api.github.com',
        'repo_api': 'https://api.github.com/repos/{owner}/{repo}',
        'zipball_api': 'https://api.github.com/repos/{owner}/{repo}/zipball',
        'auth_type': 'bearer',  # bearer, token, param
        'headers': {
            'Accept': 'application/vnd.github+json',
        },
        'env_token': 'GITHUB_TOKEN',
        'enabled': True,
        'public': True
    },
    'gitee': {
        'name': 'Gitee',
        'api_url': 'https://gitee.com/api/v5',
        'repo_api': 'https://gitee.com/api/v5/repos/{owner}/{repo}',
        'zipball_url': 'https://gitee.com/{owner}/{repo}/repository/archive/master.zip',
        'auth_type': 'param',  # Token in query parameter
        'headers': {
            'Accept': 'application/json',
        },
        'env_token': 'GITEE_TOKEN',
        'enabled': True,
        'public': True
    },
    'gitlab': {
        'name': 'GitLab',
        'api_url': 'https://gitlab.com/api/v4',
        'repo_api': 'https://gitlab.com/api/v4/projects/{owner}%2F{repo}',
        'zipball_url': 'https://gitlab.com/api/v4/projects/{owner}%2F{repo}/repository/archive.zip',
        'auth_type': 'header',  # Private-Token header
        'headers': {
            'Accept': 'application/json',
        },
        'token_header': 'PRIVATE-TOKEN',
        'env_token': 'GITLAB_TOKEN',
        'enabled': True,
        'public': True
    }
}


class GitPlatformConfig:
    """Manages Git platform configurations"""

    def __init__(self, config_file='/backend/config/git_platforms.yaml'):
        self.config_file = config_file
        self.platforms = DEFAULT_PLATFORMS.copy()
        self.load_custom_config()

    def load_custom_config(self):
        """Load custom platform configurations from YAML file or environment"""

        # Try to load from YAML file
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    custom_config = yaml.safe_load(f)
                    if custom_config and 'platforms' in custom_config:
                        for platform_id, config in custom_config['platforms'].items():
                            # Validate required fields
                            if self._validate_platform_config(platform_id, config):
                                self.platforms[platform_id] = config
                                logging.info(f"Loaded custom platform: {platform_id}")
                            else:
                                logging.warning(f"Invalid platform config: {platform_id}")
            except Exception as e:
                logging.error(f"Failed to load custom config from {self.config_file}: {e}")

        # Override with environment variables if present
        self._load_from_env()

    def _validate_platform_config(self, platform_id, config):
        """Validate platform configuration has required fields"""
        required_fields = ['name', 'api_url', 'auth_type']
        for field in required_fields:
            if field not in config:
                logging.error(f"Platform {platform_id} missing required field: {field}")
                return False

        # Must have either zipball_api, zipball_url, or use_git_clone
        has_download_method = (
            'zipball_api' in config or
            'zipball_url' in config or
            config.get('use_git_clone', False)
        )
        if not has_download_method:
            logging.error(f"Platform {platform_id} must have zipball_api, zipball_url, or use_git_clone")
            return False

        # If using git clone, must have git_url
        if config.get('use_git_clone', False) and 'git_url' not in config:
            logging.error(f"Platform {platform_id} with use_git_clone must have git_url")
            return False

        return True

    def _load_from_env(self):
        """Load platform configurations from environment variables"""
        # Example: GIT_PLATFORM_CUSTOM_NAME=MyGitLab
        #          GIT_PLATFORM_CUSTOM_API_URL=https://git.company.com/api/v4
        #          GIT_PLATFORM_CUSTOM_AUTH_TYPE=header

        platform_prefix = 'GIT_PLATFORM_'
        env_platforms = {}

        for key, value in os.environ.items():
            if key.startswith(platform_prefix):
                parts = key[len(platform_prefix):].lower().split('_', 1)
                if len(parts) == 2:
                    platform_id, field = parts
                    if platform_id not in env_platforms:
                        env_platforms[platform_id] = {}
                    env_platforms[platform_id][field] = value

        # Add validated env platforms
        for platform_id, config in env_platforms.items():
            if self._validate_platform_config(platform_id, config):
                # Set defaults
                config.setdefault('enabled', True)
                config.setdefault('public', False)
                config.setdefault('headers', {'Accept': 'application/json'})
                self.platforms[platform_id] = config
                logging.info(f"Loaded platform from env: {platform_id}")

    def get_platform(self, platform_id):
        """Get platform configuration by ID"""
        return self.platforms.get(platform_id)

    def get_enabled_platforms(self):
        """Get all enabled platforms"""
        return {k: v for k, v in self.platforms.items() if v.get('enabled', True)}

    def get_platform_list(self):
        """Get list of platforms for frontend"""
        enabled = self.get_enabled_platforms()
        platform_url_map = {
            'github': 'https://github.com/',
            'gitee': 'https://gitee.com/',
            'gitlab': 'https://gitlab.com/',
        }
        return [
            {
                'id': platform_id,
                'name': config['name'],
                'url_prefix': config.get('url_prefix', platform_url_map.get(platform_id, config['api_url'])),
                'public': config.get('public', True)
            }
            for platform_id, config in enabled.items()
        ]


# Global config instance
_config_instance = None

def get_config():
    """Get global GitPlatformConfig instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = GitPlatformConfig()
    return _config_instance


def reload_config():
    """Reload configuration (useful for development)"""
    global _config_instance
    _config_instance = None
    return get_config()
