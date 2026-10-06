---
name: rest-api-design
description: "Use when designing or reviewing REST APIs. Semantic HTTP."
context: fork
agent: general-purpose
---

# REST API Design

Adapted from sethdford/claude-skills (engineer/api-development).

Designing HTTP APIs following REST principles: resources (nouns), methods (verbs), semantic status codes, and hypermedia.

## Context

You are designing or reviewing a REST API. Your role is to:

- Identify resources in the domain
- Map CRUD operations to HTTP methods semantically
- Use status codes correctly (not 200 for errors)
- Design URLs as resources, not RPC endpoints
- Consider idempotency and caching implications

REST is architectural style, not HTTP CRUD framework. Treat it with discipline.

## Domain Context

Based on Roy Fielding's dissertation and REST maturity model (Richardson Level 0-3):

- **Resources**: Nouns (users, orders, products). Identified by URLs.
- **HTTP Methods**: GET (read), POST (create), PUT (replace all), PATCH (partial), DELETE (remove)
- **Status Codes**: 1xx (info), 2xx (success), 3xx (redirect), 4xx (client error), 5xx (server error)
- **Idempotency**: GET, PUT, DELETE are idempotent. POST is not.
- **Hypermedia**: Links in responses guide clients to related resources
- **Statelessness**: Each request contains all context needed; no session state on server

## When to Use This Skill

- Designing a new public API
- Auditing existing API for REST compliance
- Deciding between REST, gRPC, or GraphQL
- Designing complex resource hierarchies
- Handling pagination, filtering, or versioning

## Instructions

### 1. Identify Resources

Ask: "What are the nouns in this domain?"

For each resource, define:
- **Identity**: What uniquely identifies it? (id, email, SKU)
- **Relationships**: How does it relate to others? (User → many Orders)
- **Operations**: What actions apply? (CRUD + domain actions)

### 2. Design Resource Paths

```
/resource              - collection of resource
/resource/{id}        - individual resource
/resource/{id}/sub    - sub-resource (collection)
/resource/{id}/sub/{id} - individual sub-resource
```

**Good paths**:
```
GET  /users              - list all users
POST /users              - create a user
GET  /users/{id}         - fetch one user
PATCH /users/{id}        - partial update
DELETE /users/{id}       - remove
```

**Bad paths (RPC-style)**: `/getUser`, `/createOrder`, `/deleteProduct`

### 3. Map Methods Semantically

| Method | Usage | Idempotent | Safe |
|--------|-------|------------|------|
| GET | Read | yes | yes |
| POST | Create / non-idempotent actions | no | no |
| PUT | Full replace | yes | no |
| PATCH | Partial update | no* | no |
| DELETE | Remove | yes | no |

### 4. Status Codes That Mean Something

| Code | When |
|------|------|
| 200 OK | Successful GET/PATCH/PUT |
| 201 Created | POST created a resource (+ Location header) |
| 202 Accepted | Async operation started |
| 204 No Content | Successful DELETE or update with no body |
| 400 Bad Request | Malformed syntax |
| 401 Unauthorized | Missing/invalid credentials |
| 403 Forbidden | Authenticated but not allowed |
| 404 Not Found | Resource doesn't exist (don't leak existence) |
| 409 Conflict | State conflict (duplicate email) |
| 422 Unprocessable | Validation failure |
| 429 Too Many Requests | Rate limited |
| 500 Internal | Server fault (never leak stack traces) |

### 5. Error Format — One Standard, Every Endpoint

```json
{
  "error": {
    "code": "EMAIL_TAKEN",
    "message": "A user with this email already exists.",
    "details": [{ "field": "email", "issue": "duplicate" }],
    "request_id": "req_8sf9"
  }
}
```

### 6. Pagination

Offset: `?page=2&limit=20` (simple, weak under concurrent writes).
Cursor: `?cursor=abc123&limit=20` (better for distributed/large sets).

Response includes metadata:
```json
{
  "data": [],
  "pagination": { "page": 2, "limit": 20, "total": 500, "next": "/users?page=3&limit=20" }
}
```

### 7. Versioning

URL path (`/v1/`) — simplest, most visible. Header versioning for API-product polish.

### 8. Filtering / Sorting / Sparse Fields

```
GET /users?status=active&role=admin
GET /users?sort=-created_at,name
GET /users?fields=id,email
```

### 9. Document With Examples

Every endpoint: method + path, request body example, response examples (success and common errors), status codes returned.

## Decision Framework

- **REST vs GraphQL?** REST for simple CRUD; GraphQL for complex varied queries
- **Nested resources?** Keep nesting <3 levels; use query params otherwise
- **Bulk operations?** POST to collection with array of items
- **Async operations?** 202 Accepted + Location header with status endpoint

## Anti-Patterns

- Using only GET and POST (ignores PUT, DELETE, PATCH)
- Returning 200 for errors (breaks HTTP semantics)
- RPC-style URLs (/getUser instead of GET /users/{id})
- No error standardization (each endpoint different)
- Ignoring idempotency (clients can't safely retry)
- Breaking changes without versioning

## Quality Checklist

- [ ] All resources identified and mapped to nouns
- [ ] HTTP methods match CRUD/domain actions
- [ ] Status codes are semantically correct
- [ ] Error format is standardized across all endpoints
- [ ] Idempotency strategy defined for POST/async operations
- [ ] Pagination implemented for large collections
- [ ] All endpoints documented with request/response examples
- [ ] API is versioned or designed for backward compatibility

## Further Reading

- Roy Fielding, _Representational State Transfer_ (dissertation, 2000)
- Martin Fowler, _Richardson Maturity Model_
- Microsoft Azure REST API Guidelines; Google API Design Guide
- RFC 7231 (HTTP/1.1 Semantics and Content)
