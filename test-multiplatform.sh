#!/bin/bash

set -e

echo "=========================================="
echo "RecLicense Multi-Platform Test Script"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKEND_URL="http://localhost:5000"
FRONTEND_URL="http://localhost:8080"

# Functions
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=30
    local attempt=1

    print_info "Waiting for $name to be ready..."

    while [ $attempt -le $max_attempts ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            print_success "$name is ready!"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done

    print_error "$name failed to start within $(($max_attempts * 2)) seconds"
    return 1
}

test_api_endpoint() {
    local method=$1
    local endpoint=$2
    local data=$3
    local description=$4

    print_info "Testing: $description"

    if [ -n "$data" ]; then
        response=$(curl -s -X "$method" "$BACKEND_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    else
        response=$(curl -s -X "$method" "$BACKEND_URL$endpoint")
    fi

    if [ $? -eq 0 ]; then
        print_success "API call successful"
        echo "Response: $response" | head -c 200
        echo ""
        return 0
    else
        print_error "API call failed"
        return 1
    fi
}

# Main test flow
echo "Step 1: Building Docker images..."
echo "-----------------------------------"
cd /home/ubuntu/RecLicense

print_info "Building backend v1.8..."
docker build -t reclicense-backend:v1.8 -f deploy/backend.dockerfile . || {
    print_error "Backend build failed"
    exit 1
}
print_success "Backend image built"

print_info "Building frontend v1.4..."
docker build -t reclicense-frontend:v1.4 -f deploy/frontend.dockerfile . || {
    print_error "Frontend build failed"
    exit 1
}
print_success "Frontend image built"

echo ""
echo "Step 2: Starting services with docker-compose..."
echo "-----------------------------------"
docker-compose -f docker-compose.test.yaml --env-file .env.test up -d

echo ""
echo "Step 3: Waiting for services to be ready..."
echo "-----------------------------------"
wait_for_service "$BACKEND_URL/api/git_platforms" "Backend API" || exit 1
wait_for_service "$FRONTEND_URL" "Frontend" || exit 1

echo ""
echo "Step 4: Testing API endpoints..."
echo "-----------------------------------"

# Test 1: Get platform list
test_api_endpoint "GET" "/api/git_platforms" "" "Get available Git platforms"
echo ""

# Test 2: GitHub repository download
test_api_endpoint "POST" "/api/git" \
    '{"platform":"github","username":"RLinf","reponame":"RLinf"}' \
    "Download from GitHub"
echo ""

# Test 3: Gitee repository download (public repo, no token needed)
test_api_endpoint "POST" "/api/git" \
    '{"platform":"gitee","username":"geomech","reponame":"hydrate"}' \
    "Download from Gitee"
echo ""

# Test 4: GitLab repository download
test_api_endpoint "POST" "/api/git" \
    '{"platform":"gitlab","username":"gitlab-org","reponame":"gitlab-foss"}' \
    "Download from GitLab"
echo ""

# Test 5: License support list
test_api_endpoint "POST" "/api/support_list" "" "Get supported licenses"
echo ""

echo ""
echo "Step 5: Service Status..."
echo "-----------------------------------"
docker-compose -f docker-compose.test.yaml ps

echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
print_success "All services are running"
print_info "Backend URL: $BACKEND_URL"
print_info "Frontend URL: $FRONTEND_URL"
print_info ""
print_info "You can now:"
print_info "  - Visit $FRONTEND_URL in your browser"
print_info "  - Test the platform selector"
print_info "  - Check logs: docker-compose -f docker-compose.test.yaml logs -f"
print_info ""
print_info "To stop services:"
print_info "  docker-compose -f docker-compose.test.yaml down"
print_info ""
print_info "To stop and cleanup volumes:"
print_info "  docker-compose -f docker-compose.test.yaml down -v"
echo ""
