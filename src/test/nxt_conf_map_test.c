
/*
 * Copyright (C) Hong Zhi Dao
 */

#include <nxt_main.h>
#include <nxt_conf.h>
#include "nxt_tests.h"


typedef struct {
    uint8_t           guard;
    uint8_t           enabled;
    int32_t           processes;
    nxt_msec_t        timeout;
    int64_t           large;
    int               integer;
    ssize_t           size;
    off_t             offset;
    double            fraction;
    nxt_str_t         borrowed;
    nxt_str_t         copied;
    char              *terminated;
    nxt_conf_value_t  *value;
} nxt_conf_map_test_t;


nxt_int_t
nxt_conf_map_test(nxt_thread_t *thr)
{
    nxt_mp_t             *mp;
    nxt_int_t            ret;
    nxt_conf_value_t     *conf;
    nxt_conf_map_test_t  result;

    static u_char  json[] =
        "{\"enabled\":true,\"processes\":3,\"timeout\":2,"
        "\"large\":4294967296,\"integer\":-7,\"size\":4096,\"offset\":8192,"
        "\"fraction\":1.5,\"borrowed\":\"short\",\"copied\":\"copy\","
        "\"terminated\":\"terminated\",\"value\":{}}";

    static nxt_conf_map_t  map[] = {
        { nxt_string("enabled"), NXT_CONF_MAP_INT8,
          offsetof(nxt_conf_map_test_t, enabled) },
        { nxt_string("processes"), NXT_CONF_MAP_INT32,
          offsetof(nxt_conf_map_test_t, processes) },
        { nxt_string("timeout"), NXT_CONF_MAP_MSEC,
          offsetof(nxt_conf_map_test_t, timeout) },
        { nxt_string("large"), NXT_CONF_MAP_INT64,
          offsetof(nxt_conf_map_test_t, large) },
        { nxt_string("integer"), NXT_CONF_MAP_INT,
          offsetof(nxt_conf_map_test_t, integer) },
        { nxt_string("size"), NXT_CONF_MAP_SIZE,
          offsetof(nxt_conf_map_test_t, size) },
        { nxt_string("offset"), NXT_CONF_MAP_OFF,
          offsetof(nxt_conf_map_test_t, offset) },
        { nxt_string("fraction"), NXT_CONF_MAP_DOUBLE,
          offsetof(nxt_conf_map_test_t, fraction) },
        { nxt_string("borrowed"), NXT_CONF_MAP_STR,
          offsetof(nxt_conf_map_test_t, borrowed) },
        { nxt_string("copied"), NXT_CONF_MAP_STR_COPY,
          offsetof(nxt_conf_map_test_t, copied) },
        { nxt_string("terminated"), NXT_CONF_MAP_CSTRZ,
          offsetof(nxt_conf_map_test_t, terminated) },
        { nxt_string("value"), NXT_CONF_MAP_PTR,
          offsetof(nxt_conf_map_test_t, value) },
    };

    mp = nxt_mp_create(4096, 128, 512, 32);
    if (mp == NULL) {
        return NXT_ERROR;
    }

    ret = NXT_ERROR;
    nxt_memzero(&result, sizeof(result));
    result.guard = 0xA5;

    conf = nxt_conf_json_parse(mp, json, json + sizeof(json) - 1, NULL);
    if (conf == NULL) {
        goto done;
    }

    /* enabled and processes require less alignment than a union of all types. */
    if (nxt_conf_map_object(mp, conf, map, nxt_nitems(map), &result) != NXT_OK) {
        goto done;
    }

    if (result.guard != 0xA5 || result.enabled != 1 || result.processes != 3
        || result.timeout != 2000 || result.large != 4294967296LL
        || result.integer != -7 || result.size != 4096 || result.offset != 8192
        || result.fraction != 1.5
        || !nxt_str_eq(&result.borrowed, "short", 5)
        || !nxt_str_eq(&result.copied, "copy", 4)
        || result.terminated == NULL
        || strcmp(result.terminated, "terminated") != 0
        || result.value == NULL || nxt_conf_type(result.value) != NXT_CONF_OBJECT)
    {
        nxt_log_alert(thr->log, "configuration mapping test failed");
        goto done;
    }

    nxt_log_error(NXT_LOG_NOTICE, thr->log, "configuration mapping test passed");
    ret = NXT_OK;

done:

    nxt_mp_destroy(mp);

    return ret;
}
