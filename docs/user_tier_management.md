# User Pricing Tier Management

## Overview

The URL Shortener API now includes a pricing tier system with two tiers:
- **Hobby**: Default tier for all users
- **Enterprise**: Premium tier that provides access to additional features

This document describes how to manage user pricing tiers through the API.

## Features by Pricing Tier

| Feature | Hobby | Enterprise |
|---------|-------|------------|
| Create single short URL | ✓ | ✓ |
| View URL analytics | ✓ | ✓ |
| Delete short URLs | ✓ | ✓ |
| Batch URL creation | ✗ | ✓ |

## Updating a User's Pricing Tier

You can update a user's pricing tier using the following API endpoint:

```
PUT /users/{user_id}/update-tier
```

### Request Headers

| Header | Description |
|--------|-------------|
| X-API-Key | Required. Your API key for authentication |

### Request Body

```json
{
  "pricing_tier": "enterprise"  // or "hobby"
}
```

### Response

```json
{
  "user_id": 123,
  "email": "user@example.com",
  "pricing_tier": "enterprise",
  "message": "User pricing tier updated to enterprise"
}
```

### Status Codes

| Status Code | Description |
|-------------|-------------|
| 200 | User pricing tier updated successfully |
| 400 | Bad Request: Invalid pricing tier or missing required fields |
| 401 | Unauthorized: Invalid or missing API key |
| 404 | Not Found: User not found |

## Example

```bash
# Update a user to the enterprise tier
curl -X PUT \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{"pricing_tier": "enterprise"}' \
  http://localhost:5002/users/1/update-tier
```

## Notes

- Currently, only two pricing tiers are supported: `hobby` and `enterprise`
- The system is designed to be extensible for additional tiers in the future
- Users are created with the `hobby` tier by default
- Only users with valid API keys can update pricing tiers
