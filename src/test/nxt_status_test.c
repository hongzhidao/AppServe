
/*
 * Copyright (C) Zhidao HONG
 */

#include <nxt_main.h>
#include <nxt_status.h>
#include "nxt_tests.h"


static nxt_int_t nxt_status_test_check(nxt_thread_t *thr,
    nxt_status_latency_t *latency, uint64_t max, uint64_t expected95,
    uint64_t expected99);


nxt_int_t
nxt_status_test(nxt_thread_t *thr)
{
    uint64_t              lower, upper, width;
    nxt_uint_t            i, j, shift, bucket;
    nxt_status_latency_t  latency, other;

    nxt_memzero(&latency, sizeof(latency));

    if (nxt_status_test_check(thr, &latency, 0, 0, 0) != NXT_OK) {
        return NXT_ERROR;
    }

    /* Exercise both ends of every bucket, including the full uint64 range. */
    for (bucket = 0; bucket < NXT_STATUS_LATENCY_BUCKETS; bucket++) {
        if (bucket < 16) {
            lower = bucket;
            upper = bucket;

        } else {
            shift = bucket / 8 - 1;
            width = (uint64_t) 1 << shift;
            lower = (8 + bucket % 8) * width;
            upper = lower + width - 1;
        }

        nxt_memzero(&latency, sizeof(latency));
        nxt_status_latency_record(&latency, lower);
        nxt_status_latency_record(&latency, upper);

        for (i = 0; i < NXT_STATUS_LATENCY_BUCKETS; i++) {
            if (latency.buckets[i] != (i == bucket ? 2 : 0)) {
                nxt_log_alert(thr->log, "latency bucket %ui boundary failed",
                              bucket);
                return NXT_ERROR;
            }
        }

        if (nxt_status_test_check(thr, &latency, UINT64_MAX, upper, upper)
            != NXT_OK)
        {
            return NXT_ERROR;
        }

        /* A sampled max caps the reported bucket upper bound. */
        if (nxt_status_test_check(thr, &latency, lower, lower, lower)
            != NXT_OK)
        {
            return NXT_ERROR;
        }
    }

    nxt_memzero(&latency, sizeof(latency));

    for (i = 0; i < 1000; i++) {
        nxt_status_latency_record(&latency,
                                  i < 940 ? 10 : i < 980 ? 50
                                             : i < 995 ? 200 : 1000);
    }

    if (latency.sum != 19400 || latency.max != 1000) {
        nxt_log_alert(thr->log, "latency sum/max test failed");
        return NXT_ERROR;
    }

    if (nxt_status_test_check(thr, &latency, 1000, 51, 207) != NXT_OK) {
        return NXT_ERROR;
    }

    /* At exact rank boundaries, select the lower bucket. */
    nxt_memzero(&latency, sizeof(latency));

    for (i = 0; i < 100; i++) {
        nxt_status_latency_record(&latency, i < 95 ? 10 : i < 99 ? 50 : 1000);
    }

    if (nxt_status_test_check(thr, &latency, 1000, 10, 51) != NXT_OK) {
        return NXT_ERROR;
    }

    /* Application percentiles cannot be averaged to get global percentiles. */
    nxt_memzero(&latency, sizeof(latency));
    nxt_memzero(&other, sizeof(other));

    for (i = 0; i < 950; i++) {
        nxt_status_latency_record(&latency, 10);
    }

    for (i = 0; i < 50; i++) {
        nxt_status_latency_record(&other, 200);
    }

    if (nxt_status_test_check(thr, &latency, 10, 10, 10) != NXT_OK
        || nxt_status_test_check(thr, &other, 200, 200, 200) != NXT_OK)
    {
        return NXT_ERROR;
    }

    for (i = 0; i < NXT_STATUS_LATENCY_BUCKETS; i++) {
        latency.buckets[i] += other.buckets[i];
    }

    if (nxt_status_test_check(thr, &latency, 200, 10, 200) != NXT_OK) {
        return NXT_ERROR;
    }

    /* Sparse small populations round the rank up to the last sample. */
    for (i = 1; i < 20; i++) {
        nxt_memzero(&latency, sizeof(latency));

        for (j = 1; j < i; j++) {
            nxt_status_latency_record(&latency, 0);
        }

        nxt_status_latency_record(&latency, 203);

        if (nxt_status_test_check(thr, &latency, 203, 203, 203) != NXT_OK) {
            return NXT_ERROR;
        }
    }

    /* Large sample counts must not overflow percentile-rank arithmetic. */
    nxt_memzero(&latency, sizeof(latency));
    latency.buckets[0] = UINT64_MAX - UINT64_MAX / 20;
    latency.buckets[10] = UINT64_MAX / 20;

    if (nxt_status_test_check(thr, &latency, 10, 0, 10) != NXT_OK) {
        return NXT_ERROR;
    }

    nxt_log_error(NXT_LOG_NOTICE, thr->log, "status latency test passed");

    return NXT_OK;
}


static nxt_int_t
nxt_status_test_check(nxt_thread_t *thr, nxt_status_latency_t *latency,
    uint64_t max, uint64_t expected95, uint64_t expected99)
{
    uint64_t  p95, p99;

    latency->max = max;
    nxt_status_latency_percentiles(latency, &p95, &p99);

    if (p95 != expected95 || p99 != expected99) {
        nxt_log_alert(thr->log, "latency test failed: %uL/%uL, expected %uL/%uL",
                      p95, p99, expected95, expected99);
        return NXT_ERROR;
    }

    return NXT_OK;
}
