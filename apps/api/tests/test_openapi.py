def test_openapi_schema(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()

    assert spec["info"]["title"] == "Recruiting Platform API"
    assert spec["info"]["version"] == "0.1.0"

    # Paths check
    assert "/health" in spec["paths"]
    assert "/v1/chat" in spec["paths"]

    # Security schemes check
    components = spec.get("components", {})
    security_schemes = components.get("securitySchemes", {})
    assert "bearerAuth" in security_schemes
    assert security_schemes["bearerAuth"]["scheme"] == "bearer"

    # Schemas check
    schemas = components.get("schemas", {})
    assert "HealthResponse" in schemas
    assert "ChatRequest" in schemas
    assert "ChatResponse" in schemas
    assert "AgentStep" in schemas
    assert "RecordRef" in schemas
