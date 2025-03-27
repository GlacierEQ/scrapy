# API Integration

Scrapy provides a comprehensive API that allows you to integrate its functionality into your applications, automating scraping tasks programmatically. This guide covers how to use the API, whether through direct Python imports, HTTP requests, or client libraries.

## API Overview

The Scrapy API provides endpoints for:

- Basic and recursive webpage scraping
- Adaptive content extraction
- Task management
- Visualization generation
- System monitoring
- Authentication and authorization

## Authentication

API access requires authentication through API keys or JWT tokens:

### Using API Keys

```python
import requests

headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}

response = requests.get("http://localhost:8000/api/status", headers=headers)
print(response.json())
```

### Obtaining JWT Tokens

```python
import requests

# Get a token using your API key
response = requests.post(
    "http://localhost:8000/api/auth/token",
    json={"api_key": "YOUR_API_KEY"}
)

# Extract the token
token = response.json()["access_token"]

# Use the token in subsequent requests
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

response = requests.get("http://localhost:8000/api/status", headers=headers)
print(response.json())
```

## Core Endpoints

### Simple Scrape

```python
import requests

headers = {
    "Authorization": "Bearer YOUR_TOKEN",
    "Content-Type": "application/json"
}

data = {
    "url": "https://example.com",
    "compile_text": True,
    "screenshot": True,
    "save_html": True
}

response = requests.post(
    "http://localhost:8000/api/scrape/simple",
    headers=headers,
    json=data
)

result = response.json()
```

### Recursive Scrape

```python
import requests

headers = {
    "Authorization": "Bearer YOUR_TOKEN",
    "Content-Type": "application/json"
}

data = {
    "url": "https://example.com",
    "max_depth": 3,
    "max_pages": 100,
    "same_domain": True,
    "include_patterns": ["*/blog/*"],
    "exclude_patterns": ["*/author/*"],
    "async": True  # Run asynchronously
}

response = requests.post(
    "http://localhost:8000/api/scrape/recursive",
    headers=headers,
    json=data
)

task = response.json()
task_id = task["task_id"]

# Check task status later
task_status = requests.get(
    f"http://localhost:8000/api/tasks/{task_id}",
    headers=headers
)
```

### Adaptive Scrape

```python
import requests

headers = {
    "Authorization": "Bearer YOUR_TOKEN",
    "Content-Type": "application/json"
}

data = {
    "url": "https://example.com/products",
    "data_type": "product",  # Specify the type of content to extract
    "use_ai": True,  # Use AI for better extraction
    "async": False   # Run synchronously
}

response = requests.post(
    "http://localhost:8000/api/scrape/adaptive",
    headers=headers,
    json=data
)

result = response.json()
```

## Task Management

### List Tasks

```python
import requests

headers = {
    "Authorization": "Bearer YOUR_TOKEN"
}

# Get all tasks with pagination
response = requests.get(
    "http://localhost:8000/api/tasks?limit=20&offset=0",
    headers=headers
)

tasks = response.json()["tasks"]

# Filter by status
response = requests.get(
    "http://localhost:8000/api/tasks?status=in_progress",
    headers=headers
)

in_progress_tasks = response.json()["tasks"]
```

### Get Task Details

```python
import requests

headers = {
    "Authorization": "Bearer YOUR_TOKEN"
}

response = requests.get(
    f"http://localhost:8000/api/tasks/{task_id}",
    headers=headers
)

task_details = response.json()
```

### Cancel Task

```python
import requests

headers = {
    "Authorization": "Bearer YOUR_TOKEN"
}

response = requests.post(
    f"http://localhost:8000/api/tasks/{task_id}/cancel",
    headers=headers
)

result = response.json()
```

## Results and Downloads

### Get Results

```python
import requests

headers = {
    "Authorization": "Bearer YOUR_TOKEN"
}

response = requests.get(
    f"http://localhost:8000/api/results/{task_id}",
    headers=headers
)

results = response.json()["results"]
```

### Download Results in Different Formats

```python
import requests

headers = {
    "Authorization": "Bearer YOUR_TOKEN"
}

# Get the download URL
response = requests.get(
    f"http://localhost:8000/api/download/{task_id}?format=csv",
    headers=headers
)

# Use the provided URL to download the file
download_url = response.json()["download_url"]
download = requests.get(download_url)

# Save to file
with open("results.csv", "wb") as f:
    f.write(download.content)
```

## Visual Builder

```python
import requests

headers = {
    "Authorization": "Bearer YOUR_TOKEN",
    "Content-Type": "application/json"
}

data = {
    "url": "https://example.com",
    "headless": False  # Show the browser for visual selection
}

response = requests.post(
    "http://localhost:8000/api/visual-builder/start",
    headers=headers,
    json=data
)

session = response.json()
session_id = session["session_id"]
```

## Using the Python Client Library

For Python applications, Scrapy provides a convenient client library that handles authentication, request formatting, and response parsing:

```python
from scrapy_client import ScrapyClient

# Initialize client
client = ScrapyClient(
    base_url="http://localhost:8000/api",
    api_key="YOUR_API_KEY"
)

# Check API status
status = client.get_status()

# Perform a simple scrape
result = client.simple_scrape(
    url="https://example.com",
    compile_text=True,
    screenshot=True
)

# Perform an adaptive scrape
data = client.adaptive_scrape(
    url="https://example.com/products",
    data_type="product",
    use_ai=True
)

# Recursive scrape with waiting for completion
recursive_result = client.scrape_and_wait(
    url="https://example.com",
    scrape_type="recursive",
    max_depth=2,
    max_pages=50,
    same_domain=True
)

# Scrape multiple URLs in parallel
results = client.extract_from_multiple_pages(
    urls=["https://example.com/page1", "https://example.com/page2"],
    scrape_type="adaptive",
    parallel=True
)
```

## Building Custom API Clients

If you need to write a client in another programming language, here's what you need to implement:

1. **Authentication Handling**:
   - Token-based authentication
   - Auto-refreshing of expired tokens

2. **Request Construction**:
   - JSON payload formatting
   - Proper headers

3. **Response Parsing**:
   - JSON parsing
   - Error handling

4. **Task Management**:
   - Polling for task completion
   - Task result retrieval

## Rate Limiting

The API implements rate limiting to ensure fair usage. Limits vary by endpoint:

| Endpoint | Rate Limit |
|----------|------------|
| Simple scrape | 20 calls per minute |
| Recursive scrape | 5 calls per minute |
| Adaptive scrape | 10 calls per minute |
| Visual builder | 5 calls per minute |

When a rate limit is exceeded, the API returns a `429 Too Many Requests` response with a `Retry-After` header indicating when you can make the next request.

## Error Handling

The API uses standard HTTP status codes and includes detailed error information in responses:

```json
{
  "error": "Rate limit exceeded: 20 calls per 60 seconds",
  "code": "rate_limit_exceeded"
}
```

Common error codes include:

- `auth_required`: Authentication is missing
- `invalid_token`: Token is invalid or expired
- `invalid_api_key`: API key is not valid
- `rate_limit_exceeded`: Too many requests
- `task_not_found`: The specified task does not exist
- `scraping_error`: An error occurred during scraping

## WebSocket for Real-Time Updates

For real-time updates on task progress, Scrapy provides WebSocket connections:

```javascript
// JavaScript example
const socket = new WebSocket('ws://localhost:8000/ws');

socket.onopen = function(event) {
  console.log('Connected to WebSocket server');
  // Subscribe to task updates
  socket.send(JSON.stringify({
    type: 'subscribe',
    task_id: 'YOUR_TASK_ID'
  }));
};

socket.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('Update received:', data);
  
  if (data.status === 'completed') {
    // Task is complete, fetch results
  }
};
```

## Security Best Practices

1. **Store API Keys Securely**:
   - Use environment variables or secure vaults
   - Never hardcode keys in source code

2. **Implement Token Refresh Logic**:
   - Check token expiration
   - Refresh before expiry

3. **Use HTTPS**:
   - Always use HTTPS for API communication
   - Verify SSL certificates

4. **Implement Request Timeout**:
   - Set reasonable timeouts for API requests
   - Handle timeout exceptions gracefully

## Next Steps

- Explore the complete [API Reference](../reference/api.md)
- Learn how to [deploy your own API server](../advanced/deployment.md)
- Check out [client library examples](../tools/python_client.md)
- See how to [integrate with other services](../advanced/integration.md)
