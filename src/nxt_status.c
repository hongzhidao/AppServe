
/*
 * Copyright (C) NGINX, Inc.
 * Copyright (C) Zhidao HONG
 */

#include <nxt_main.h>
#include <nxt_conf.h>
#include <nxt_status.h>


nxt_conf_value_t *
nxt_status_get(nxt_status_report_t *report, nxt_mp_t *mp)
{
    size_t            i, j;
    uint64_t          count, p95, p99;
    nxt_str_t         name;
    nxt_int_t         ret;
    nxt_status_app_t  *app;
    nxt_conf_value_t  *status, *obj, *apps, *app_obj;

    static nxt_str_t active_str = nxt_string("active");
    static nxt_str_t reqs_str = nxt_string("requests");
    static nxt_str_t total_str = nxt_string("total");
    static nxt_str_t completed_str = nxt_string("completed");
    static nxt_str_t failed_str = nxt_string("failed");
    static nxt_str_t apps_str = nxt_string("applications");
    static nxt_str_t procs_str = nxt_string("processes");
    static nxt_str_t max_str = nxt_string("max");
    static nxt_str_t spare_str = nxt_string("spare");
    static nxt_str_t busy_str = nxt_string("busy");
    static nxt_str_t idle_str = nxt_string("idle");
    static nxt_str_t responses_str = nxt_string("responses");
    static nxt_str_t latency_str = nxt_string("latency");
    static nxt_str_t sum_str = nxt_string("sum");
    static nxt_str_t avg_str = nxt_string("avg");
    static nxt_str_t p95_str = nxt_string("p95");
    static nxt_str_t p99_str = nxt_string("p99");
    static nxt_str_t response_classes[] = {
        nxt_string("1xx"),
        nxt_string("2xx"),
        nxt_string("3xx"),
        nxt_string("4xx"),
        nxt_string("5xx"),
    };

    status = nxt_conf_create_object(mp, 5);
    if (nxt_slow_path(status == NULL)) {
        return NULL;
    }

    obj = nxt_conf_create_object(mp, 4);
    if (nxt_slow_path(obj == NULL)) {
        return NULL;
    }

    nxt_conf_set_member(status, &reqs_str, obj, 0);

    nxt_conf_set_member_integer(obj, &total_str, report->total_requests, 0);
    nxt_conf_set_member_integer(obj, &active_str, report->active_requests, 1);
    nxt_conf_set_member_integer(obj, &completed_str, report->completed_requests,
                                2);
    nxt_conf_set_member_integer(obj, &failed_str, report->failed_requests, 3);

    apps = nxt_conf_create_object(mp, report->apps_count);
    if (nxt_slow_path(apps == NULL)) {
        return NULL;
    }

    nxt_conf_set_member(status, &apps_str, apps, 1);

    for (i = 0; i < report->apps_count; i++) {
        app = &report->apps[i];

        app_obj = nxt_conf_create_object(mp, 4);
        if (nxt_slow_path(app_obj == NULL)) {
            return NULL;
        }

        name.length = app->name.length;
        name.start = nxt_pointer_to(report, (uintptr_t) app->name.start);

        ret = nxt_conf_set_member_dup(apps, mp, &name, app_obj, i);
        if (nxt_slow_path(ret != NXT_OK)) {
            return NULL;
        }

        obj = nxt_conf_create_object(mp, 4);
        if (nxt_slow_path(obj == NULL)) {
            return NULL;
        }

        nxt_conf_set_member(app_obj, &procs_str, obj, 0);

        nxt_conf_set_member_integer(obj, &max_str, app->max_processes, 0);
        nxt_conf_set_member_integer(obj, &spare_str, app->spare_processes, 1);
        nxt_conf_set_member_integer(obj, &busy_str, app->busy_processes, 2);
        nxt_conf_set_member_integer(obj, &idle_str, app->idle_processes, 3);

        obj = nxt_conf_create_object(mp, 4);
        if (nxt_slow_path(obj == NULL)) {
            return NULL;
        }

        nxt_conf_set_member(app_obj, &reqs_str, obj, 1);

        nxt_conf_set_member_integer(obj, &total_str, app->total_requests, 0);
        nxt_conf_set_member_integer(obj, &active_str, app->active_requests, 1);
        nxt_conf_set_member_integer(obj, &completed_str, app->completed_requests,
                                    2);
        nxt_conf_set_member_integer(obj, &failed_str, app->failed_requests, 3);

        obj = nxt_conf_create_object(mp, nxt_nitems(response_classes));
        if (nxt_slow_path(obj == NULL)) {
            return NULL;
        }

        nxt_conf_set_member(app_obj, &responses_str, obj, 2);

        for (j = 0; j < nxt_nitems(response_classes); j++) {
            nxt_conf_set_member_integer(obj, &response_classes[j],
                                        app->responses[j], j);
        }

        obj = nxt_conf_create_object(mp, 5);
        if (nxt_slow_path(obj == NULL)) {
            return NULL;
        }

        count = app->completed_requests + app->failed_requests;
        nxt_status_latency_percentiles(&app->latency, &p95, &p99);
        nxt_conf_set_member(app_obj, &latency_str, obj, 3);
        nxt_conf_set_member_integer(obj, &sum_str, app->latency.sum, 0);
        nxt_conf_set_member_integer(obj, &avg_str,
                                    count != 0 ? app->latency.sum / count : 0, 1);
        nxt_conf_set_member_integer(obj, &max_str, app->latency.max, 2);
        nxt_conf_set_member_integer(obj, &p95_str, p95, 3);
        nxt_conf_set_member_integer(obj, &p99_str, p99, 4);
    }

    obj = nxt_conf_create_object(mp, 2);
    if (nxt_slow_path(obj == NULL)) {
        return NULL;
    }

    nxt_conf_set_member(status, &procs_str, obj, 2);
    nxt_conf_set_member_integer(obj, &busy_str, report->busy_processes, 0);
    nxt_conf_set_member_integer(obj, &idle_str, report->idle_processes, 1);

    obj = nxt_conf_create_object(mp, nxt_nitems(response_classes));
    if (nxt_slow_path(obj == NULL)) {
        return NULL;
    }

    nxt_conf_set_member(status, &responses_str, obj, 3);

    for (j = 0; j < nxt_nitems(response_classes); j++) {
        nxt_conf_set_member_integer(obj, &response_classes[j],
                                    report->responses[j], j);
    }

    obj = nxt_conf_create_object(mp, 5);
    if (nxt_slow_path(obj == NULL)) {
        return NULL;
    }

    count = report->completed_requests + report->failed_requests;
    nxt_status_latency_percentiles(&report->latency, &p95, &p99);
    nxt_conf_set_member(status, &latency_str, obj, 4);
    nxt_conf_set_member_integer(obj, &sum_str, report->latency.sum, 0);
    nxt_conf_set_member_integer(obj, &avg_str,
                                count != 0 ? report->latency.sum / count : 0, 1);
    nxt_conf_set_member_integer(obj, &max_str, report->latency.max, 2);
    nxt_conf_set_member_integer(obj, &p95_str, p95, 3);
    nxt_conf_set_member_integer(obj, &p99_str, p99, 4);

    return status;
}


void
nxt_status_latency_percentiles(const nxt_status_latency_t *latency,
    uint64_t *p95, uint64_t *p99)
{
    uint64_t    count, rank95, rank99, cumulative, upper;
    nxt_uint_t  i, shift;

    count = 0;

    for (i = 0; i < NXT_STATUS_LATENCY_BUCKETS; i++) {
        count += latency->buckets[i];
    }

    *p95 = 0;
    *p99 = 0;

    if (count == 0) {
        return;
    }

    /* Nearest ranks, without overflowing count * percentile. */
    rank95 = count - count / 20;
    rank99 = count - count / 100;
    cumulative = 0;

    for (i = 0; i < NXT_STATUS_LATENCY_BUCKETS; i++) {
        cumulative += latency->buckets[i];

        if (cumulative < rank95) {
            continue;
        }

        if (i < 16) {
            upper = i;

        } else {
            shift = i / 8 - 1;
            upper = ((uint64_t) (8 + i % 8) << shift)
                    | (((uint64_t) 1 << shift) - 1);
        }

        if (rank95 != 0) {
            *p95 = nxt_min(upper, latency->max);
            rank95 = 0;
        }

        if (cumulative >= rank99) {
            *p99 = nxt_min(upper, latency->max);
            return;
        }
    }
}
