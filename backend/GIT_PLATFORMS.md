# RecLicense Multi-Platform Git Support

RecLicense now supports downloading and analyzing repositories from **GitHub**, **Gitee**, and **GitLab**.

## Supported Platforms

### 1. GitHub (github.com)
- **API Endpoint**: `https://api.github.com`
- **Token**: Set via `GITHUB_TOKEN` environment variable or `app/token_github` file
- **Public Repos**: Token optional but recommended to avoid rate limits
- **Private Repos**: Token required

### 2. Gitee (gitee.com)
- **API Endpoint**: `https://gitee.com/api/v5`
- **Token**: Set via `GITEE_TOKEN` environment variable or `app/token_gitee` file
- **Public Repos**: No token required
- **Private Repos**: Token required

### 3. GitLab (gitlab.com)
- **API Endpoint**: `https://gitlab.com/api/v4`
- **Token**: Set via `GITLAB_TOKEN` environment variable or `app/token_gitlab` file
- **Public Repos**: No token required
- **Private Repos**: Token required

## API Usage

### Endpoint: `/api/git` or `/api/git_c`

**Method**: POST

**Request Body**:
```json
{
  "username": "owner-name",
  "reponame": "repository-name",
  "platform": "github"  // Optional: "github", "gitee", or "gitlab" (default: "github")
}
```

### Examples

#### GitHub Repository
```bash
curl -X POST http://localhost:5000/api/git \
  -H "Content-Type: application/json" \
  -d '{
    "username": "osslab-pku",
    "reponame": "RecLicense",
    "platform": "github"
  }'
```

#### Gitee Repository
```bash
curl -X POST http://localhost:5000/api/git \
  -H "Content-Type: application/json" \
  -d '{
    "username": "mirrors",
    "reponame": "linux",
    "platform": "gitee"
  }'
```

#### GitLab Repository
```bash
curl -X POST http://localhost:5000/api/git \
  -H "Content-Type: application/json" \
  -d '{
    "username": "gitlab-org",
    "reponame": "gitlab",
    "platform": "gitlab"
  }'
```

#### Backward Compatibility (GitHub only)
```bash
curl -X POST http://localhost:5000/api/git \
  -H "Content-Type: application/json" \
  -d '{
    "username": "osslab-pku",
    "reponame": "RecLicense"
  }'
```
*Note: When `platform` is omitted, defaults to GitHub*

## Token Configuration

### Method 1: Environment Variables (Recommended for Kubernetes)

Set tokens in deployment.yaml or secrets:
```yaml
env:
- name: GITHUB_TOKEN
  value: "ghp_your_github_token"
- name: GITEE_TOKEN
  value: "your_gitee_token"
- name: GITLAB_TOKEN
  value: "glpat_your_gitlab_token"
```

### Method 2: Token Files

Create token files in `backend/app/` directory:

**GitHub**: `app/token_github`
```
ghp_token1
ghp_token2
ghp_token3
```

**Gitee**: `app/token_gitee`
```
gitee_token1
gitee_token2
```

**GitLab**: `app/token_gitlab`
```
glpat_token1
glpat_token2
```

*Note: Multiple tokens per file are supported; one will be selected randomly for load balancing*

## Token Generation

### GitHub Personal Access Token
1. Go to https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Select scopes: `repo` (for private repos) or none (for public repos)
4. Copy the generated token

### Gitee Personal Access Token
1. Go to https://gitee.com/profile/personal_access_tokens
2. Click "生成新令牌" (Generate new token)
3. Select scopes: `projects` (for repository access)
4. Copy the generated token

### GitLab Personal Access Token
1. Go to https://gitlab.com/-/profile/personal_access_tokens
2. Create a new token with `read_repository` scope
3. Copy the generated token

## Features

### Auto-Detection
The system can auto-detect the platform from owner/repo format:
```python
download_git("github.com/owner", "repo")  # Detects GitHub
download_git("gitee.com/owner", "repo")   # Detects Gitee
download_git("gitlab.com/owner", "repo")  # Detects GitLab
```

### Error Handling
- Returns `"URL ERROR"` if repository not found
- Returns `"URL ERROR"` if download fails
- Logs detailed error messages for debugging

### Logging
All download attempts are logged to `app/logging/backend.log`:
```
2025-11-26 10:30:15 [INFO] Downloading from github: osslab-pku/RecLicense
2025-11-26 10:30:18 [INFO] Successfully downloaded github repository: osslab-pku/RecLicense
```

## Deployment Notes

### Kubernetes Secret Configuration

Update `apps/reclicense/deployment.yaml`:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: reclicense-config
  namespace: reclicense
type: Opaque
stringData:
  GITHUB_TOKEN: "YOUR_GITHUB_TOKEN_HERE"
  GITEE_TOKEN: "YOUR_GITEE_TOKEN_HERE"    # Add this
  GITLAB_TOKEN: "YOUR_GITLAB_TOKEN_HERE"  # Add this
  MONGO_HOST: "mongodb"
  MONGO_PORT: "27017"
  REACT_APP_BASE_URL: "http://localhost:5000"
```

Then apply the secret:
```bash
kubectl apply -f apps/reclicense/deployment.yaml
kubectl rollout restart deployment/reclicense-backend -n reclicense
```

## Testing

Test each platform:

```bash
# Test GitHub
curl -X POST http://10.100.6.201:30600/api/git \
  -H "Content-Type: application/json" \
  -d '{"username": "osslab-pku", "reponame": "RecLicense", "platform": "github"}'

# Test Gitee
curl -X POST http://10.100.6.201:30600/api/git \
  -H "Content-Type: application/json" \
  -d '{"username": "mirrors", "reponame": "linux", "platform": "gitee"}'

# Test GitLab
curl -X POST http://10.100.6.201:30600/api/git \
  -H "Content-Type: application/json" \
  -d '{"username": "gitlab-org", "reponame": "gitlab-foss", "platform": "gitlab"}'
```

## Troubleshooting

### "URL ERROR" Response

1. **Check token configuration**: Verify tokens are set correctly
2. **Check repository exists**: Verify owner/repo names are correct
3. **Check logs**: Review `app/logging/backend.log` for detailed errors
4. **Check network**: Ensure pods can access external Git platforms
5. **Check rate limits**: GitHub has API rate limits (60/hour without token, 5000/hour with token)

### Token Not Found Error

```
Exception: No github token found, please set GITHUB_TOKEN or create app/token_github
```

**Solution**: Set token via environment variable or create token file as described above.

## Code Structure

```
backend/app/
├── download_git.py          # Multi-platform download module
├── routes.py                # API endpoints with platform support
├── token_github (optional)  # GitHub tokens
├── token_gitee (optional)   # Gitee tokens
└── token_gitlab (optional)  # GitLab tokens
```

## Migration from Old Code

The new code is **backward compatible**. Existing API calls without `platform` parameter will default to GitHub:

**Old code** (still works):
```json
{"username": "owner", "reponame": "repo"}
```

**New code** (recommended):
```json
{"username": "owner", "reponame": "repo", "platform": "github"}
```

## Version

- **RecLicense Backend**: v1.8+
- **Supported Platforms**: GitHub, Gitee, GitLab
- **Kubernetes Deployment**: Compatible with existing deployment
