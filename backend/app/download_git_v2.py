"""
Multi-platform Git repository download module
Supports configurable Git platforms (GitHub, GitLab, Gitee, and private deployments)
"""

import subprocess
import os
import datetime
import random
import json
import logging
import shutil
from .git_platforms_config import get_config

logging.basicConfig(
    filename=f"./app/logging/backend.log",
    filemode='a',
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)


def get_token(platform_config):
    """Get token for the specified Git platform from file or environment"""
    platform_id = platform_config.get('id', 'unknown')
    env_var = platform_config.get('env_token')

    # Try to get token from file first
    token_file = f'./app/token_{platform_id}'
    if os.path.exists(token_file):
        try:
            with open(token_file, "r") as f:
                tokens = f.readlines()
                tokens = list(map(lambda e: e.strip(), tokens))
                tokens = [t for t in tokens if t]  # Filter empty lines
                if tokens:
                    return tokens[random.randint(0, len(tokens) - 1)]
        except Exception as e:
            logging.warning(f"Failed to read token file {token_file}: {e}")

    # Try to get token from environment variable
    if env_var:
        token = os.environ.get(env_var)
        if token:
            return token

    # Token is optional for public repos on some platforms
    return None


def build_auth_headers(platform_config, token):
    """Build authentication headers based on platform config"""
    headers = platform_config.get('headers', {}).copy()
    auth_type = platform_config.get('auth_type', 'bearer')

    if not token:
        return headers

    if auth_type == 'bearer':
        headers['Authorization'] = f'Bearer {token}'
    elif auth_type == 'header':
        token_header = platform_config.get('token_header', 'Authorization')
        token_prefix = platform_config.get('token_prefix', '')
        headers[token_header] = f'{token_prefix}{token}'

    # For 'param' type, token is added to URL query string, not headers

    return headers


def download_via_git_clone(owner, repo, platform, platform_config, token, filepath):
    """
    Download repository using git clone (for platforms that require it)

    Args:
        owner: Repository owner/username
        repo: Repository name
        platform: Platform ID
        platform_config: Platform configuration dict
        token: Authentication token
        filepath: Directory to store the downloaded repo

    Returns:
        Path to created zip file or 'URL ERROR' on failure
    """
    if not token:
        logging.error(f"Token required for git clone on platform {platform}")
        return 'URL ERROR'

    try:
        # Replace slashes in owner name for directory/file naming
        safe_owner = owner.replace('/', '-')

        # Build git URL with embedded token
        git_url_template = platform_config.get('git_url', 'https://oauth2:{token}@{host}/{owner}/{repo}.git')
        git_url = git_url_template.format(token=token, owner=owner, repo=repo)

        # Clone directory
        clone_dir = f"{filepath}/{safe_owner}_{repo}_clone"

        # Get default branch
        default_branch = platform_config.get('default_branch', 'master')

        # Execute git clone
        clone_cmd = ["git", "clone", "--depth", "1", "--branch", default_branch, git_url, clone_dir]

        logging.info(f"Cloning {platform} repository: {owner}/{repo} (branch: {default_branch})")
        pipe = subprocess.Popen(clone_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return_code = pipe.wait()
        out = pipe.communicate()

        if return_code != 0:
            logging.error(f"Git clone failed: {out[1].decode()}")
            return 'URL ERROR'

        # Create zip from cloned directory
        zip_path = f"{filepath}/{safe_owner}_{repo}"
        shutil.make_archive(zip_path, 'zip', clone_dir)
        zip_file = f"{zip_path}.zip"

        # Clean up clone directory
        shutil.rmtree(clone_dir, ignore_errors=True)

        if os.path.exists(zip_file) and os.path.getsize(zip_file) > 0:
            logging.info(f"Successfully cloned and zipped {platform} repository: {owner}/{repo} ({os.path.getsize(zip_file)} bytes)")
            return zip_file
        else:
            logging.error(f"Failed to create zip file from clone")
            return 'URL ERROR'

    except Exception as e:
        logging.error(f"Error during git clone: {str(e)}")
        return 'URL ERROR'


def download_git(owner, repo, platform='github'):
    """
    Download repository from configured Git platform

    Args:
        owner: Repository owner/username
        repo: Repository name
        platform: Platform ID (e.g., 'github', 'gitee', 'gitlab', 'gitlab-private')

    Returns:
        Path to downloaded zip file or 'URL ERROR' on failure
    """
    config = get_config()
    platform_config = config.get_platform(platform)

    if not platform_config:
        logging.error(f"Platform not found or not enabled: {platform}")
        return 'URL ERROR'

    if not platform_config.get('enabled', True):
        logging.error(f"Platform is disabled: {platform}")
        return 'URL ERROR'

    try:
        # Get token for the platform
        token = get_token({**platform_config, 'id': platform})

        # Create filepath
        filepath = "./temp_files/" + str(datetime.datetime.now())
        os.makedirs(filepath, exist_ok=True)

        # Check if this platform uses git clone instead of zip download
        if platform_config.get('use_git_clone', False):
            return download_via_git_clone(owner, repo, platform, platform_config, token, filepath)

        # Prepare headers
        headers = build_auth_headers(platform_config, token)
        auth_type = platform_config.get('auth_type', 'bearer')

        # Step 1: Verify repository exists and get default branch (if repo_api is configured)
        default_branch = 'master'  # Default fallback
        repo_info = None

        if 'repo_api' in platform_config:
            repo_api_url = platform_config['repo_api'].format(owner=owner, repo=repo)

            # Add query params for 'param' auth type
            if auth_type == 'param' and token:
                token_param_name = platform_config.get('token_param', 'access_token')
                separator = '&' if '?' in repo_api_url else '?'
                repo_api_url += f'{separator}{token_param_name}={token}'

            # Build curl command for repo verification
            curl_cmd = ["curl", "-s"]

            for key, value in headers.items():
                if value:  # Only add non-None headers
                    curl_cmd.extend(["-H", f"{key}: {value}"])

            curl_cmd.append(repo_api_url)

            logging.info(f"Verifying {platform} repository: {owner}/{repo}")
            pipe = subprocess.Popen(curl_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return_code = pipe.wait()
            out = pipe.communicate()

            if return_code != 0:
                logging.error(f"Failed to verify repository: {out[1].decode()}")
                return 'URL ERROR'

            try:
                response = json.loads(out[0])
                repo_info = response
                # Check for error messages
                if isinstance(response, dict):
                    error_msgs = ['Not Found', '404 Not Found', '404 Project Not Found']
                    if response.get("message") in error_msgs:
                        logging.error(f"Repository not found: {owner}/{repo}")
                        return 'URL ERROR'

                    # Get default branch from API response if configured
                    if platform_config.get('fetch_default_branch', False):
                        default_branch_field = platform_config.get('default_branch_field', 'default_branch')
                        if default_branch_field in response:
                            default_branch = response[default_branch_field]
                            logging.info(f"Detected default branch: {default_branch}")
            except json.JSONDecodeError:
                logging.warning("Could not parse API response as JSON")

        # Step 2: Download repository zipball
        # Get zipball URL template
        if 'zipball_api' in platform_config:
            zipball_url_template = platform_config['zipball_api']
        elif 'zipball_url' in platform_config:
            zipball_url_template = platform_config['zipball_url']
        else:
            logging.error(f"Platform {platform} has no zipball_api or zipball_url configured")
            return 'URL ERROR'

        # Prepare branch list for fallback
        branch_list = [default_branch] if default_branch else []
        if 'branch_fallback' in platform_config:
            # Add fallback branches that aren't already in the list
            for branch in platform_config['branch_fallback']:
                if branch not in branch_list:
                    branch_list.append(branch)

        if not branch_list:
            branch_list = ['master']  # Ultimate fallback

        # Replace slashes in owner name to avoid path issues
        safe_owner = owner.replace('/', '-')
        safe_repo = repo.replace('/', '-')
        zip_path = f"{filepath}/{safe_owner}_{safe_repo}.zip"

        # Try each branch until one succeeds
        for branch in branch_list:
            logging.info(f"Trying branch '{branch}' for {platform}: {owner}/{repo}")

            zipball_url = zipball_url_template.format(owner=owner, repo=repo, branch=branch)

            # Use download-specific auth if configured, otherwise use default auth
            download_auth_type = platform_config.get('download_auth_type', auth_type)
            download_headers = headers.copy()

            if download_auth_type == 'param' and token:
                # Add token to URL
                token_param_name = platform_config.get('token_param', 'access_token')
                separator = '&' if '?' in zipball_url else '?'
                zipball_url += f'{separator}{token_param_name}={token}'
            elif download_auth_type == 'header' and token:
                # Add token to headers
                download_token_header = platform_config.get('download_token_header', 'Authorization')
                download_token_prefix = platform_config.get('download_token_prefix', '')
                download_headers[download_token_header] = f'{download_token_prefix}{token}'

            # Build download command
            download_cmd = ["curl", "-L", "-s", "-w", "%{http_code}"]

            for key, value in download_headers.items():
                if value:
                    download_cmd.extend(["-H", f"{key}: {value}"])

            download_cmd.extend([zipball_url, "-o", zip_path])

            pipe = subprocess.Popen(download_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return_code = pipe.wait()
            out = pipe.communicate()

            if return_code == 0:
                http_code = out[0].decode().strip()
                # Verify the zip file was created and has content
                if os.path.exists(zip_path) and os.path.getsize(zip_path) > 0 and http_code == '200':
                    logging.info(f"Successfully downloaded {platform} repository: {owner}/{repo} (branch: {branch}, {os.path.getsize(zip_path)} bytes)")
                    return zip_path
                else:
                    logging.warning(f"Branch '{branch}' failed (HTTP {http_code}), trying next...")
                    # Clean up failed download
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
            else:
                logging.warning(f"Download failed for branch '{branch}': {out[1].decode()}")

        # All branches failed
        logging.error(f"Failed to download {platform} repository {owner}/{repo} - tried branches: {', '.join(branch_list)}")
        return 'URL ERROR'

    except Exception as e:
        logging.error(f"Error downloading from {platform}: {str(e)}")
        return 'URL ERROR'


# Backward compatibility
def download_github(owner, repo):
    """Backward compatibility wrapper for GitHub"""
    return download_git(owner, repo, platform='github')


if __name__ == "__main__":
    # Test examples
    config = get_config()
    print("Available platforms:")
    for platform in config.get_platform_list():
        print(f"  - {platform['id']}: {platform['name']} (public={platform['public']})")

    print("\nTesting GitHub:")
    result = download_git("osslab-pku", "RecLicense", "github")
    print(f"GitHub result: {result}")
