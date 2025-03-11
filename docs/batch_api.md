# URL Shortener Batch API

## Overview

The URL Shortener Batch API allows you to create multiple short URLs in a single request. This is useful for bulk processing of URLs, saving time and reducing the number of API calls needed.

> **Note:** This endpoint is only available to users on the **Enterprise** pricing tier. Users on the **Hobby** tier will receive a 403 Forbidden response when attempting to use this endpoint.

## Endpoint

```
POST /shorten/batch
```

## Authentication

Authentication is required via API key. Include your API key in the request headers:

```
X-API-Key: your_api_key_here
```

## Request Format

The request body should be a JSON object with a single `urls` property containing an array of URL objects:

```json
{
  "urls": [
    {
      "url": "https://example.com/page1",
      "custom_code": "page1",      // Optional
      "expiry_date": "2026-01-01T00:00:00",  // Optional, ISO format
      "timeout_seconds": 3600       // Optional
    },
    {
      "url": "https://example.com/page2"
      // Minimal required fields
    },
    // More URLs...
  ]
}
```

### URL Object Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `url` | String | Yes | The original URL to shorten |
| `custom_code` | String | No | A custom code for the short URL (1-6 alphanumeric characters or hyphens) |
| `expiry_date` | String | No | ISO format date when the URL will expire (e.g., "2026-01-01T00:00:00") |
| `timeout_seconds` | Integer | No | Number of seconds of inactivity after which the URL will time out |

## Response Format

The response is a JSON object containing information about the batch processing results:

```json
{
  "total": 3,           // Total number of URLs in the request
  "successful": 2,      // Number of successfully created URLs
  "failed": 1,          // Number of failed URLs
  "results": [          // Array of results for each URL
    {
      "original_url": "https://example.com/page1",
      "success": true,
      "short_code": "page1",
      "short_url": "http://localhost:5002/redirect?code=page1",
      "expiry_date": "2026-01-01T00:00:00",
      "timeout_seconds": 3600
    },
    {
      "original_url": "https://example.com/page2",
      "success": true,
      "short_code": "abc123",
      "short_url": "http://localhost:5002/redirect?code=abc123",
      "expiry_date": null,
      "timeout_seconds": null
    },
    {
      "original_url": "",
      "success": false,
      "error": "URL cannot be empty",
      "status_code": 400
    }
  ]
}
```

### Result Object Properties

For successful URLs:

| Property | Type | Description |
|----------|------|-------------|
| `original_url` | String | The original URL that was shortened |
| `success` | Boolean | Always `true` for successful URLs |
| `short_code` | String | The short code generated or provided |
| `short_url` | String | The complete short URL |
| `expiry_date` | String | ISO format date when the URL will expire, or `null` |
| `timeout_seconds` | Integer | Timeout in seconds, or `null` |

For failed URLs:

| Property | Type | Description |
|----------|------|-------------|
| `original_url` | String | The original URL that failed |
| `success` | Boolean | Always `false` for failed URLs |
| `error` | String | Error message explaining why the URL failed |
| `status_code` | Integer | HTTP status code for the error |

## Status Codes

| Status Code | Description |
|-------------|-------------|
| 200 | All URLs were successfully created |
| 207 | Multi-Status: Some URLs were created, others failed |
| 400 | Bad Request: All URLs failed or request format was invalid |
| 401 | Unauthorized: Invalid or missing API key |
| 403 | Forbidden: User does not have the required pricing tier (Enterprise) |

## Limitations

- Maximum batch size: 100 URLs per request
- Only available to users on the Enterprise pricing tier
- Rate limiting may apply depending on your account type

## Examples

### Example Request

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key_here" \
  -d '{
    "urls": [
      {
        "url": "https://example.com/page1",
        "custom_code": "page1"
      },
      {
        "url": "https://example.com/page2",
        "timeout_seconds": 3600
      }
    ]
  }' \
  http://localhost:5003/shorten/batch
```

### Example Response

```json
{
  "total": 2,
  "successful": 2,
  "failed": 0,
  "results": [
    {
      "original_url": "https://example.com/page1",
      "success": true,
      "short_code": "page1",
      "short_url": "http://localhost:5002/redirect?code=page1",
      "expiry_date": null,
      "timeout_seconds": null
    },
    {
      "original_url": "https://example.com/page2",
      "success": true,
      "short_code": "abc123",
      "short_url": "http://localhost:5002/redirect?code=abc123",
      "expiry_date": null,
      "timeout_seconds": 3600
    }
  ]
}
```
