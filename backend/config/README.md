# Git Platforms Configuration

This directory contains configuration files for custom Git platforms.

## Quick Start

1. Copy the example configuration:
   ```bash
   cp git_platforms.yaml.example git_platforms.yaml
   ```

2. Edit `git_platforms.yaml` to add your private Git platforms

3. Set environment variables for tokens in Kubernetes Secret or `.env`

4. Restart the backend service

## Configuration Files

- `git_platforms.yaml.example` - Example configuration with all supported options
- `git_platforms.yaml` - Your actual configuration (gitignored, not committed)

## Configuration Methods

### Method 1: YAML File (Recommended)

Create `/backend/config/git_platforms.yaml`:

```yaml
platforms:
  gitlab-private:
    name: "Company GitLab"
    api_url: "https://gitlab.company.com/api/v4"
    repo_api: "https://gitlab.company.com/api/v4/projects/{owner}%2F{repo}"
    zipball_url: "https://gitlab.company.com/api/v4/projects/{owner}%2F{repo}/repository/archive.zip"
    auth_type: header
    token_header: "PRIVATE-TOKEN"
    headers:
      Accept: "application/json"
    env_token: "GITLAB_PRIVATE_TOKEN"
    enabled: true
    public: false
```

### Method 2: Environment Variables

Set environment variables with prefix `GIT_PLATFORM_`:

```bash
GIT_PLATFORM_MYGIT_NAME="My GitLab"
GIT_PLATFORM_MYGIT_API_URL="https://git.company.com/api/v4"
GIT_PLATFORM_MYGIT_AUTH_TYPE="header"
GIT_PLATFORM_MYGIT_ZIPBALL_URL="https://git.company.com/api/v4/projects/{owner}%2F{repo}/repository/archive.zip"
```

### Method 3: Kubernetes ConfigMap

Mount YAML as ConfigMap:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: git-platforms-config
  namespace: reclicense
data:
  git_platforms.yaml: |
    platforms:
      gitlab-private:
        name: "Company GitLab"
        api_url: "https://gitlab.company.com/api/v4"
        ...
---
# Mount in deployment
volumeMounts:
- name: git-config
  mountPath: /backend/config
volumes:
- name: git-config
  configMap:
    name: git-platforms-config
```

## Supported Git Platforms

### Built-in Platforms

- **GitHub** (`github`) - https://github.com
- **Gitee** (`gitee`) - https://gitee.com
- **GitLab** (`gitlab`) - https://gitlab.com

### Compatible Private Platforms

- **GitLab CE/EE** - Self-hosted GitLab
- **Gitea** - Lightweight self-hosted Git service
- **Gogs** - Painless self-hosted Git service
- **GitHub Enterprise** - Enterprise GitHub
- **Bitbucket Server** - With API v1.0+
- **Azure DevOps** - With REST API

## Token Configuration

### Set Tokens via Environment Variables

```yaml
# In Kubernetes Secret
apiVersion: v1
kind: Secret
metadata:
  name: reclicense-config
stringData:
  GITHUB_TOKEN: "ghp_xxxxx"
  GITEE_TOKEN: "xxxxx"
  GITLAB_TOKEN: "glpat_xxxxx"
  GITLAB_PRIVATE_TOKEN: "glpat_xxxxx"  # For private GitLab
  GITEA_TOKEN: "xxxxx"
```

### Set Tokens via File

Create token files in `/backend/app/`:

```bash
echo "ghp_your_token" > /backend/app/token_github
echo "your_token" > /backend/app/token_gitlab-private
echo "your_token" > /backend/app/token_gitea
```

## Testing Configuration

Test the API endpoint:

```bash
# Get list of available platforms
curl http://localhost:5000/api/git_platforms

# Response example:
{
  "platforms": [
    {"id": "github", "name": "GitHub", "public": true},
    {"id": "gitee", "name": "Gitee", "public": true},
    {"id": "gitlab", "name": "GitLab", "public": true},
    {"id": "gitlab-private", "name": "Company GitLab", "public": false}
  ]
}
```

Test downloading:

```bash
curl -X POST http://localhost:5000/api/git \
  -H "Content-Type: application/json" \
  -d '{
    "username": "owner",
    "reponame": "repo",
    "platform": "gitlab-private"
  }'
```

## Troubleshooting

### Platform not showing in list

1. Check YAML syntax: `python -m yaml git_platforms.yaml`
2. Check logs: `tail -f /backend/app/logging/backend.log`
3. Verify `enabled: true` in config

### Download fails with "URL ERROR"

1. Check repository exists and is accessible
2. Verify API URLs are correct (test in browser/curl)
3. Check token has correct permissions
4. Review logs for detailed error messages

### Token not found

1. Verify environment variable name matches `env_token` in config
2. Check token file exists: `ls /backend/app/token_*`
3. Restart backend after changing tokens

## Security Notes

1. **Never commit tokens** - Use .gitignore for `token_*` files and `git_platforms.yaml`
2. **Use Kubernetes Secrets** for production token management
3. **Rotate tokens** regularly for security
4. **Limit token permissions** to repository read access only
5. **Use private platforms** for sensitive code repositories
