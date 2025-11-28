#!/usr/bin/env python3
"""
Benchmark script for Memory Engine with 10K embeddings
Tests insertion, query performance, and HNSW index effectiveness
"""

import time
import numpy as np
from memory_engine import MemoryEngine, generate_random_embeddings

def main():
    print("=" * 70)
    print("Memory Engine Benchmark - 10K Embeddings")
    print("=" * 70)

    # Configuration
    n_vectors = 10000
    n_queries = 100
    k_results = 10

    print(f"\nConfiguration:")
    print(f"  Vectors: {n_vectors:,}")
    print(f"  Queries: {n_queries}")
    print(f"  Results per query (k): {k_results}")

    with MemoryEngine() as engine:
        # Clear existing data
        print(f"\n1. Clearing existing data...")
        with engine.conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE memory_vectors")
            engine.conn.commit()
        print(f"   Cleared. Starting fresh.")

        # Generate embeddings
        print(f"\n2. Generating {n_vectors:,} random 1024-dim embeddings...")
        start = time.perf_counter()
        embeddings = generate_random_embeddings(n_vectors)
        gen_time = time.perf_counter() - start
        print(f"   Generated in {gen_time:.2f}s ({n_vectors/gen_time:.0f} vectors/sec)")

        # Prepare batch data
        print(f"\n3. Preparing batch data...")
        vectors = [
            (
                f"bench_vec_{i:06d}",
                embeddings[i],
                f"Benchmark vector {i} with some sample content for testing",
                {"index": i, "category": f"cat_{i % 10}", "batch": i // 1000}
            )
            for i in range(n_vectors)
        ]

        # Insert vectors
        print(f"\n4. Inserting {n_vectors:,} vectors...")
        start = time.perf_counter()
        engine.batch_insert(vectors, batch_size=1000, verbose=True)
        insert_time = time.perf_counter() - start
        print(f"   Total insertion time: {insert_time:.2f}s")
        print(f"   Throughput: {n_vectors/insert_time:.0f} vectors/sec")

        # Get database stats
        print(f"\n5. Database statistics:")
        stats = engine.stats()
        print(f"   Total vectors: {stats['total_vectors']:,}")
        print(f"   Table size: {stats['table_size']}")
        print(f"   Index size: {stats['index_size']}")

        # Run query benchmark
        print(f"\n6. Running {n_queries} queries...")
        latencies = []

        # Use random vectors from our dataset as queries
        query_indices = np.random.choice(n_vectors, n_queries, replace=False)

        for i, idx in enumerate(query_indices):
            results, latency = engine.query(embeddings[idx], k=k_results)
            latencies.append(latency)

            # Progress indicator
            if (i + 1) % 10 == 0:
                avg_so_far = np.mean(latencies)
                print(f"   Completed {i+1}/{n_queries} queries (avg: {avg_so_far:.2f}ms)")

        # Analyze results
        latencies = np.array(latencies)
        print(f"\n7. Query Performance Results:")
        print(f"   Mean latency:   {np.mean(latencies):.2f}ms")
        print(f"   Median latency: {np.median(latencies):.2f}ms")
        print(f"   P95 latency:    {np.percentile(latencies, 95):.2f}ms")
        print(f"   P99 latency:    {np.percentile(latencies, 99):.2f}ms")
        print(f"   Min latency:    {np.min(latencies):.2f}ms")
        print(f"   Max latency:    {np.max(latencies):.2f}ms")
        print(f"   Std deviation:  {np.std(latencies):.2f}ms")

        # Test accuracy - first query should return exact match
        print(f"\n8. Testing accuracy (first query)...")
        results, latency = engine.query(embeddings[0], k=5)
        print(f"   Query latency: {latency:.2f}ms")
        print(f"   Top 5 results:")
        for i, result in enumerate(results):
            print(f"     {i+1}. {result['vector_id']}: score={result['score']:.4f}")

        # Check if exact match is first
        if results[0]['vector_id'] == 'bench_vec_000000' and results[0]['score'] > 0.999:
            print(f"   ✅ Exact match found as top result!")
        else:
            print(f"   ⚠️  Exact match not found as top result")

        # Performance assessment
        print(f"\n9. Performance Assessment:")
        mean_latency = np.mean(latencies)
        if mean_latency < 10:
            print(f"   ✅ EXCELLENT: Mean latency {mean_latency:.2f}ms < 10ms target")
        elif mean_latency < 50:
            print(f"   ⚠️  GOOD: Mean latency {mean_latency:.2f}ms < 50ms")
        else:
            print(f"   ❌ SLOW: Mean latency {mean_latency:.2f}ms > 50ms")

        print(f"\n{'=' * 70}")
        print(f"Benchmark complete!")
        print(f"{'=' * 70}")

if __name__ == '__main__':
    main()
