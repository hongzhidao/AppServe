
/*
 * Copyright (C) Hong Zhi Dao
 */

#include <nxt_router.h>
#include <nxt_http.h>
#include <nxt_http_forwarded.h>
#include "nxt_tests.h"


static nxt_int_t nxt_http_forwarded_test_run(nxt_thread_t *thr,
    nxt_str_t *value, nxt_str_t *expected, const char *peer, nxt_int_t scheme);
static nxt_int_t nxt_http_forwarded_test_large(nxt_thread_t *thr);


nxt_int_t
nxt_http_forwarded_test(nxt_thread_t *thr)
{
    size_t      len;
    uint32_t    random;
    nxt_uint_t  i, j;
    nxt_str_t   value;

    static struct {
        nxt_str_t  value;
        nxt_str_t  address;
        nxt_int_t  scheme;

    } tests[] = {
        { nxt_string("for=203.0.113.9;proto=https"),
          nxt_string("203.0.113.9"), 1 },
        { nxt_string("for=203.0.113.9;proto=https, for=10.20.0.2"),
          nxt_string("203.0.113.9"), 1 },
        { nxt_string("for=203.0.113.9;proto=https, for=invalid"),
          nxt_string("192.0.2.2"), 0 },
        { nxt_string("for=\"203.0.113.9\0evil\";proto=https"),
          nxt_string("192.0.2.2"), 0 },
        { nxt_string("for=203.0.113.9;proto=\"https\x7F\""),
          nxt_string("192.0.2.2"), 0 },
        { nxt_string("for=203.0.113.9;ext=\"\x01\";proto=https"),
          nxt_string("192.0.2.2"), 0 },
        { nxt_string("for=203.0.113.9;ext=\"\xFF\";proto=https"),
          nxt_string("203.0.113.9"), 1 },
        { nxt_string("for=203.0.113.9;ext=\"a\\\"b,c\";proto=https"),
          nxt_string("203.0.113.9"), 1 },
        { nxt_string("for=203.0.113.9;ext=\"a\\\\\";proto=https"),
          nxt_string("203.0.113.9"), 1 },
        { nxt_string("for=203.0.113.9;proto=https;ext=\"\\\""),
          nxt_string("192.0.2.2"), 0 },
        { nxt_string("for=203.0.113.9;proto=https;ext=\"\\\x7F\""),
          nxt_string("192.0.2.2"), 0 },
        { nxt_string("for=203.0.113.9;proto=https;EXT=a;ext=b"),
          nxt_string("192.0.2.2"), 0 },
    };

    u_char  bytes[256];

    for (i = 0; i < nxt_nitems(tests); i++) {
        if (nxt_http_forwarded_test_run(thr, &tests[i].value,
                                       &tests[i].address, "127.0.0.1",
                                       tests[i].scheme) != NXT_OK)
        {
            return NXT_ERROR;
        }
    }

    value = tests[0].value;

    /* Authorization uses the immutable peer, not the effective remote. */
    if (nxt_http_forwarded_test_run(thr, &value, &tests[2].address,
                                   "192.0.2.1", 0) != NXT_OK)
    {
        return NXT_ERROR;
    }

#if (NXT_INET6)
    if (nxt_http_forwarded_test_run(thr, &value, &tests[0].address,
                                   "::ffff:127.0.0.1", 1) != NXT_OK)
    {
        return NXT_ERROR;
    }
#endif

    /* Exercise every truncation with an exact-sized, non-terminated buffer. */
    for (i = 0; i < nxt_nitems(tests); i++) {
        value = tests[i].value;

        for (len = 0; len < tests[i].value.length; len++) {
            value.length = len;

            if (nxt_http_forwarded_test_run(thr, &value, NULL,
                                           "127.0.0.1", -1) != NXT_OK)
            {
                return NXT_ERROR;
            }
        }
    }

    random = 0x7239;
    value.start = bytes;

    for (i = 0; i < 10000; i++) {
        value.length = i % sizeof(bytes);

        for (j = 0; j < value.length; j++) {
            random ^= random << 13;
            random ^= random >> 17;
            random ^= random << 5;
            bytes[j] = random;
        }

        if (value.length >= nxt_length("for=\"")) {
            nxt_memcpy(bytes, "for=\"", nxt_length("for=\""));
        }

        if (nxt_http_forwarded_test_run(thr, &value, NULL,
                                       "127.0.0.1", -1) != NXT_OK)
        {
            return NXT_ERROR;
        }
    }

    if (nxt_http_forwarded_test_large(thr) != NXT_OK) {
        return NXT_ERROR;
    }

    nxt_log_error(NXT_LOG_NOTICE, thr->log, "http forwarded test passed");

    return NXT_OK;
}


static nxt_int_t
nxt_http_forwarded_test_run(nxt_thread_t *thr, nxt_str_t *value,
    nxt_str_t *expected, const char *peer, nxt_int_t scheme)
{
    u_char                *bytes;
    nxt_mp_t              *mp;
    nxt_int_t             ret;
    nxt_str_t             addr;
    nxt_conf_value_t      *conf;
    nxt_http_field_t      *field;
    nxt_http_request_t    r;
    nxt_http_addr_rule_t  *trusted;

    static u_char  config[] = "[\"127.0.0.1\",\"10.20.0.0/16\"]";

    bytes = malloc(nxt_max(value->length, 1));
    mp = nxt_mp_create(4096, 128, 512, 32);
    ret = NXT_ERROR;

    if (bytes == NULL || mp == NULL) {
        goto done;
    }

    nxt_memcpy(bytes, value->start, value->length);
    nxt_memzero(&r, sizeof(r));
    r.mem_pool = mp;
    addr.start = (u_char *) peer;
    addr.length = nxt_strlen(peer);
    r.peer = nxt_sockaddr_parse_optport(mp, &addr);
    nxt_str_set(&addr, "192.0.2.2");
    r.remote = nxt_sockaddr_parse_optport(mp, &addr);
    r.fields = nxt_list_create(mp, 1, sizeof(nxt_http_field_t));
    conf = nxt_conf_json_parse(mp, config, config + sizeof(config) - 1, NULL);

    if (r.peer == NULL || r.remote == NULL || r.fields == NULL || conf == NULL) {
        goto done;
    }

    trusted = nxt_http_addr_rule_create(mp, conf);
    field = nxt_list_zero_add(r.fields);

    if (trusted == NULL || field == NULL) {
        goto done;
    }

    nxt_http_field_name_set(field, "Forwarded");
    field->value = bytes;
    field->value_length = value->length;

    if (nxt_http_forwarded(&r, trusted) != NXT_OK
        || nxt_memcmp(bytes, value->start, value->length) != 0)
    {
        goto done;
    }

    if (expected != NULL
        && !nxt_str_eq(expected, nxt_sockaddr_address(r.remote),
                       r.remote->address_length))
    {
        goto done;
    }

    if (scheme >= 0 && r.https != scheme) {
        goto done;
    }

    addr.start = (u_char *) peer;
    addr.length = nxt_strlen(peer);
    if (!nxt_str_eq(&addr, nxt_sockaddr_address(r.peer), r.peer->address_length)) {
        goto done;
    }

    ret = NXT_OK;

done:

    if (ret != NXT_OK) {
        nxt_log_alert(thr->log, "http forwarded test failed for \"%V\"", value);
    }

    if (mp != NULL) {
        nxt_mp_destroy(mp);
    }

    free(bytes);

    return ret;
}


static nxt_int_t
nxt_http_forwarded_test_large(nxt_thread_t *thr)
{
    size_t     i;
    nxt_int_t  ret;
    nxt_str_t  value;

    static nxt_str_t  expected = nxt_string("192.0.2.2");

    value.length = 4 * (UINT16_MAX / 2 + 1);
    value.start = malloc(value.length);
    if (value.start == NULL) {
        return NXT_ERROR;
    }

    nxt_memset(value.start, ',', value.length);
    ret = nxt_http_forwarded_test_run(thr, &value, &expected, "127.0.0.1", 0);

    if (ret == NXT_OK) {
        for (i = 0; i < value.length; i += 4) {
            nxt_memcpy(value.start + i, "x=a;", 4);
        }

        ret = nxt_http_forwarded_test_run(thr, &value, &expected,
                                          "127.0.0.1", 0);
    }

    free(value.start);

    return ret;
}
