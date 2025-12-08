"""Simple test script to verify idempotency middleware."""

import asyncio

import httpx


async def test_idempotency() -> None:
    """Test idempotency middleware with duplicate requests."""
    base_url = "http://localhost:8000"

    # Generate a unique idempotency key
    import uuid

    idempotency_key = str(uuid.uuid4())

    print(f"Testing idempotency with key: {idempotency_key}\n")

    async with httpx.AsyncClient() as client:
        # Test 1: Send first request
        print("1. Sending first request...")
        response1 = await client.post(f"{base_url}/api/config/reload", headers={"Idempotency-Key": idempotency_key})
        print(f"   Status: {response1.status_code}")
        print(f"   Cache header: {response1.headers.get('X-Idempotency-Cache', 'MISS')}")

        # Test 2: Send duplicate request (should return cached response)
        print("\n2. Sending duplicate request...")
        response2 = await client.post(f"{base_url}/api/config/reload", headers={"Idempotency-Key": idempotency_key})
        print(f"   Status: {response2.status_code}")
        print(f"   Cache header: {response2.headers.get('X-Idempotency-Cache', 'MISS')}")
        print(f"   Cached at: {response2.headers.get('X-Idempotency-Cached-At', 'N/A')}")

        # Test 3: Send request with different key (should not use cache)
        print("\n3. Sending request with different key...")
        new_key = str(uuid.uuid4())
        response3 = await client.post(f"{base_url}/api/config/reload", headers={"Idempotency-Key": new_key})
        print(f"   Status: {response3.status_code}")
        print(f"   Cache header: {response3.headers.get('X-Idempotency-Cache', 'MISS')}")

        # Verify responses match
        print("\n4. Verification:")
        print(f"   Response 1 == Response 2: {response1.json() == response2.json()}")
        print(f"   Response 2 was cached: {response2.headers.get('X-Idempotency-Cache') == 'HIT'}")


if __name__ == "__main__":
    print("=" * 60)
    print("Idempotency Middleware Test")
    print("=" * 60)
    print("\nMake sure the server is running on http://localhost:8000\n")

    try:
        asyncio.run(test_idempotency())
        print("\n✅ Test completed successfully!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
