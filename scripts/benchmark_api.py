import time
import requests

BASE_URL = "http://localhost:8000"

def run_benchmarks():
    print("=" * 60)
    print("🚀 RUNNING API PERFORMANCE BENCHMARK")
    print("=" * 60)

    # 1. First GET /api/checksheets (cold query if cache expired or fresh)
    t0 = time.perf_counter()
    r = requests.get(f"{BASE_URL}/api/checksheets?limit=1000")
    t1 = time.perf_counter()
    items = r.json()
    count = len(items)
    print(f"1. GET /api/checksheets (First/Cold Fetch):   {(t1 - t0)*1000:8.2f} ms ({count} items returned, status: {r.status_code})")

    # 2. Second GET /api/checksheets (Warm In-Memory Cache)
    t0 = time.perf_counter()
    r = requests.get(f"{BASE_URL}/api/checksheets?limit=1000")
    t1 = time.perf_counter()
    print(f"2. GET /api/checksheets (Warm In-Memory Cache): {(t1 - t0)*1000:8.2f} ms")

    # 3. Third GET /api/checksheets with filter
    t0 = time.perf_counter()
    r = requests.get(f"{BASE_URL}/api/checksheets?assigned_to=Zul&limit=1000")
    t1 = time.perf_counter()
    print(f"3. GET /api/checksheets?assigned_to=Zul (Filtered Cache): {(t1 - t0)*1000:8.2f} ms ({len(r.json())} items)")

    # Find a sample checksheet to test PUT
    sample_id = items[0]["id"]
    original_ket = items[0].get("keterangan") or ""
    new_ket = f"Benchmark update {int(time.time())}"

    # 4. PUT /api/checksheets/{id} (Update single field)
    t0 = time.perf_counter()
    r = requests.put(f"{BASE_URL}/api/checksheets/{sample_id}", json={"keterangan": new_ket})
    t1 = time.perf_counter()
    print(f"4. PUT /api/checksheets/{sample_id} (Field Update):      {(t1 - t0)*1000:8.2f} ms (status: {r.status_code})")

    # 5. Immediate GET /api/checksheets after PUT (Should still be warm in-memory with new data!)
    t0 = time.perf_counter()
    r = requests.get(f"{BASE_URL}/api/checksheets?limit=1000")
    t1 = time.perf_counter()
    updated_items = r.json()
    sample_in_cache = next((x for x in updated_items if x["id"] == sample_id), None)
    is_updated = sample_in_cache and sample_in_cache["keterangan"] == new_ket
    print(f"5. GET /api/checksheets (Post-PUT Cache Hit):   {(t1 - t0)*1000:8.2f} ms (Consistent: {is_updated})")

    # Revert keterangan
    requests.put(f"{BASE_URL}/api/checksheets/{sample_id}", json={"keterangan": original_ket})

    # 6. Test CREATE, DELETE, and BULK-DELETE performance
    # Create 3 test checksheets
    test_ids = []
    print("\n--- Testing Mutation Cycle (Create, Single Delete, Bulk Delete) ---")
    for i in range(3):
        t0 = time.perf_counter()
        r = requests.post(f"{BASE_URL}/api/checksheets/manual", json={
            "part_number": f"BENCH-TEST-{i}-{int(time.time())}",
            "part_name": f"Benchmark Part {i}",
            "model": "TEST-MODEL",
            "customer": "TEST-CUST",
            "doc_number": "DOC-TEST",
            "status": "Belum di review",
            "assigned_to": "Unassigned",
            "keterangan": "Temporary test part for benchmark",
            "points": [
                {"item_no": "1", "inspection_item": "Visual Test 1", "standard": "OK", "method": "Visual"},
                {"item_no": "2", "inspection_item": "Dimension Test 2", "standard": "10mm", "method": "Caliper"}
            ]
        })
        t1 = time.perf_counter()
        created = r.json()
        test_ids.append(created["id"])
        print(f"6.{i+1} POST /api/checksheets (Create #{created['id']}):   {(t1 - t0)*1000:8.2f} ms")

    # Verify cache contains newly created part without cold refetch
    t0 = time.perf_counter()
    r = requests.get(f"{BASE_URL}/api/checksheets?limit=1000")
    t1 = time.perf_counter()
    has_test = any(x["id"] == test_ids[0] for x in r.json())
    print(f"7. GET /api/checksheets (Immediately after Create): {(t1 - t0)*1000:8.2f} ms (Contains new part: {has_test})")

    # Single Delete test
    del_id = test_ids.pop(0)
    t0 = time.perf_counter()
    r = requests.delete(f"{BASE_URL}/api/checksheets/{del_id}")
    t1 = time.perf_counter()
    print(f"8. DELETE /api/checksheets/{del_id} (Single Delete):   {(t1 - t0)*1000:8.2f} ms (status: {r.status_code})")

    # Bulk Delete test for remaining 2
    t0 = time.perf_counter()
    r = requests.post(f"{BASE_URL}/api/checksheets/bulk-delete", json={"checksheet_ids": test_ids})
    t1 = time.perf_counter()
    print(f"9. POST /api/checksheets/bulk-delete ({len(test_ids)} parts): {(t1 - t0)*1000:8.2f} ms (status: {r.status_code})")

    # Verify cache has removed the parts without cold refetch
    t0 = time.perf_counter()
    r = requests.get(f"{BASE_URL}/api/checksheets?limit=1000")
    t1 = time.perf_counter()
    cleaned = not any(x["id"] in [del_id] + test_ids for x in r.json())
    print(f"10. GET /api/checksheets (Immediately after Delete): {(t1 - t0)*1000:8.2f} ms (Cleaned: {cleaned})")

    print("=" * 60)
    print("✅ BENCHMARK COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    run_benchmarks()
