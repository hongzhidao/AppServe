
/*
 * Copyright (C) NGINX, Inc.
 * Copyright (C) Zhidao HONG
 */

#ifndef _NXT_STATUS_H_INCLUDED_
#define _NXT_STATUS_H_INCLUDED_


#include <nxt_conf.h>


/* Millisecond buckets: exact below 16, then eight per power-of-two range. */
#define NXT_STATUS_LATENCY_BUCKETS  (16 + (64 - 4) * 8)


typedef struct {
    uint64_t  sum;
    uint64_t  max;
    uint64_t  buckets[NXT_STATUS_LATENCY_BUCKETS];
} nxt_status_latency_t;


typedef struct {
    nxt_str_t             name;
    uint64_t              total_requests;
    uint64_t              completed_requests;
    uint64_t              failed_requests;
    uint64_t              responses[5];
    nxt_status_latency_t  latency;
    uint64_t              crash_processes;
    uint32_t              active_requests;
    uint32_t              queued_requests;
    uint32_t              max_processes;
    uint32_t              spare_processes;
    uint32_t              busy_processes;
    uint32_t              idle_processes;
} nxt_status_app_t;


typedef struct {
    uint64_t              total_requests;
    uint64_t              active_requests;
    uint64_t              queued_requests;
    uint64_t              completed_requests;
    uint64_t              failed_requests;
    uint64_t              busy_processes;
    uint64_t              idle_processes;
    uint64_t              crash_processes;
    uint64_t              responses[5];
    nxt_status_latency_t  latency;

    size_t                apps_count;
    nxt_status_app_t      apps[];
} nxt_status_report_t;


nxt_conf_value_t *nxt_status_get(nxt_status_report_t *report, nxt_mp_t *mp);
void nxt_status_latency_percentiles(const nxt_status_latency_t *latency,
    uint64_t *p95, uint64_t *p99);


/* Latency updates are intentionally unsynchronized. */
nxt_inline void
nxt_status_latency_record(nxt_status_latency_t *latency, uint64_t elapsed)
{
    nxt_uint_t  shift;

    shift = 0;

    latency->sum += elapsed;
    latency->max = nxt_max(latency->max, elapsed);

    while (elapsed >= 16) {
        elapsed >>= 1;
        shift++;
    }

    latency->buckets[shift * 8 + elapsed]++;
}


#endif /* _NXT_STATUS_H_INCLUDED_ */
