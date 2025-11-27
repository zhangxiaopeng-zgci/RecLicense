import subprocess
import os
import datetime
import random
import json
import logging

logging.basicConfig(
    filename=f"./app/logging/backend.log",
    filemode='a',
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)

# Git platform configurations
GIT_PLATFORMS = {
    'github': {
        'api_url': 'https://api.github.com',
        'repo_api': 'https://api.github.com/repos/{owner}/{repo}',
        'zipball_api': 'https://api.github.com/repos/{owner}/{repo}/zipball',
        'headers': lambda token: {
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {token}' if token else None
        },
        'env_token': 'GITHUB_TOKEN'
    },
    'gitee': {
        'api_url': 'https://gitee.com/api/v5',
        'repo_api': 'https://gitee.com/api/v5/repos/{owner}/{repo}',
        'zipball_url': 'https://gitee.com/{owner}/{repo}/repository/archive/master.zip',
        'headers': lambda token: {
            'Accept': 'application/json',
        },
        'query_params': lambda token: f'?access_token={token}' if token else '',
        'env_token': 'GITEE_TOKEN'
    },
    'gitlab': {
        'api_url': 'https://gitlab.com/api/v4',
        'repo_api': 'https://gitlab.com/api/v4/projects/{owner}%2F{repo}',
        'zipball_url': 'https://gitlab.com/api/v4/projects/{owner}%2F{repo}/repository/archive.zip',
        'headers': lambda token: {
            'Accept': 'application/json',
            'PRIVATE-TOKEN': token if token else None
        },
        'env_token': 'GITLAB_TOKEN'
    }
}


def get_token(platform='github'):
    """Get token for the specified Git platform from file or environment"""
    # Try to get token from file first
    token_file = f'./app/token_{platform}'
    if os.path.exists(token_file):
        with open(token_file, "r") as f:
            tokens = f.readlines()
            tokens = list(map(lambda e: e.strip(), tokens))
            return tokens[random.randint(0, len(tokens) - 1)]

    # Try to get token from environment variable
    env_var = GIT_PLATFORMS[platform]['env_token']
    token = os.environ.get(env_var)

    if not token and platform == 'github':
        # GitHub token is required
        raise Exception(f'No {platform} token found, please set {env_var} or create {token_file}')

    return token


def detect_platform(owner, repo):
    """Auto-detect Git platform from owner/repo format"""
    # If owner contains domain, extract platform
    if '/' in owner and '.' in owner:
        # Format like: github.com/owner or gitee.com/owner
        parts = owner.split('/')
        domain = parts[0].lower()
        if 'github' in domain:
            return 'github', parts[1] if len(parts) > 1 else owner
        elif 'gitee' in domain:
            return 'gitee', parts[1] if len(parts) > 1 else owner
        elif 'gitlab' in domain:
            return 'gitlab', parts[1] if len(parts) > 1 else owner

    # Default to GitHub for backward compatibility
    return 'github', owner


def download_git(owner, repo, platform='auto'):
    """
    Download repository from GitHub, Gitee, or GitLab

    Args:
        owner: Repository owner/username
        repo: Repository name
        platform: Git platform ('github', 'gitee', 'gitlab', or 'auto')

    Returns:
        Path to downloaded zip file or 'URL ERROR' on failure
    """
    # Auto-detect platform if needed
    if platform == 'auto':
        platform, owner = detect_platform(owner, repo)

    platform = platform.lower()

    if platform not in GIT_PLATFORMS:
        logging.error(f"Unsupported platform: {platform}")
        return 'URL ERROR'

    config = GIT_PLATFORMS[platform]

    try:
        # Get token for the platform
        token = get_token(platform)

        # Create filepath
        filepath = "./temp_files/" + str(datetime.datetime.now())
        os.makedirs(filepath, exist_ok=True)

        # Prepare headers
        headers = config['headers'](token)

        # Step 1: Verify repository exists (only for platforms with API)
        if 'repo_api' in config:
            repo_api_url = config['repo_api'].format(owner=owner, repo=repo)

            # Add query params for Gitee
            if platform == 'gitee' and 'query_params' in config:
                repo_api_url += config['query_params'](token)

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
                # Check for error messages
                if isinstance(response, dict):
                    if response.get("message") == 'Not Found' or response.get("message") == '404 Not Found':
                        logging.error(f"Repository not found: {owner}/{repo}")
                        return 'URL ERROR'
            except json.JSONDecodeError:
                logging.warning("Could not parse API response as JSON")

        # Step 2: Download repository zipball
        if platform == 'github':
            zipball_url = config['zipball_api'].format(owner=owner, repo=repo)
            download_cmd = ["curl", "-L", "-H", f"Accept: {headers['Accept']}"]
            if headers.get('Authorization'):
                download_cmd.extend(["-H", f"Authorization: {headers['Authorization']}"])
            download_cmd.extend([zipball_url, "-o", f"{filepath}/{owner}_{repo}.zip"])

        elif platform == 'gitee':
            zipball_url = config['zipball_url'].format(owner=owner, repo=repo)
            if token:
                zipball_url += f'?access_token={token}'
            download_cmd = ["curl", "-L", zipball_url, "-o", f"{filepath}/{owner}_{repo}.zip"]

        elif platform == 'gitlab':
            zipball_url = config['zipball_url'].format(owner=owner, repo=repo)
            download_cmd = ["curl", "-L"]
            if headers.get('PRIVATE-TOKEN'):
                download_cmd.extend(["-H", f"PRIVATE-TOKEN: {headers['PRIVATE-TOKEN']}"])
            download_cmd.extend([zipball_url, "-o", f"{filepath}/{owner}_{repo}.zip"])

        logging.info(f"Downloading from {platform}: {owner}/{repo}")
        pipe = subprocess.Popen(download_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return_code = pipe.wait()
        out = pipe.communicate()

        if return_code == 0:
            zip_path = f"{filepath}/{owner}_{repo}.zip"
            # Verify the zip file was created and has content
            if os.path.exists(zip_path) and os.path.getsize(zip_path) > 0:
                logging.info(f"Successfully downloaded {platform} repository: {owner}/{repo}")
                return zip_path
            else:
                logging.error(f"Downloaded file is empty or does not exist")
                return 'URL ERROR'
        else:
            logging.error(f"Download failed with return code {return_code}: {out[1].decode()}")
            return 'URL ERROR'

    except Exception as e:
        logging.error(f"Error downloading from {platform}: {str(e)}")
        return 'URL ERROR'


def download_github(owner, repo):
    """Backward compatibility wrapper for GitHub"""
    return download_git(owner, repo, platform='github')


# For backward compatibility
download_git_github = download_github


if __name__ == "__main__":
    # Test examples
    print("Testing GitHub:")
    result = download_git("osslab-pku", "RecLicense", "github")
    print(f"GitHub result: {result}")

    # Uncomment to test other platforms
    # print("\nTesting Gitee:")
    # result = download_git("owner", "repo", "gitee")
    # print(f"Gitee result: {result}")

    # print("\nTesting GitLab:")
    # result = download_git("owner", "repo", "gitlab")
    # print(f"GitLab result: {result}")
