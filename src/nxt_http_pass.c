
/*
 * Copyright (C) Igor Sysoev
 * Copyright (C) NGINX, Inc.
 * Copyright (C) Hong Zhidao
 */

#include <nxt_router.h>
#include <nxt_http.h>


static void nxt_http_pass_var(nxt_task_t *task, nxt_http_request_t *r,
    nxt_http_pass_t *pass);
static nxt_int_t nxt_http_pass_find(nxt_mp_t *mp, nxt_router_conf_t *rtcf,
    nxt_str_t *value, nxt_http_pass_t *pass);


nxt_http_pass_t *
nxt_http_pass_create(nxt_router_temp_conf_t *tmcf, nxt_str_t *value)
{
    nxt_int_t          ret;
    nxt_str_t          str;
    nxt_http_pass_t    *pass;
    nxt_router_conf_t  *rtcf;

    rtcf = tmcf->router_conf;

    pass = nxt_mp_zalloc(rtcf->mem_pool, sizeof(nxt_http_pass_t));
    if (nxt_slow_path(pass == NULL)) {
        return NULL;
    }

    pass->u.tstr = nxt_tstr_compile(rtcf->tstr_state, value, 0);
    if (nxt_slow_path(pass->u.tstr == NULL)) {
        return NULL;
    }

    if (nxt_tstr_is_const(pass->u.tstr)) {
        nxt_tstr_str(pass->u.tstr, &str);

        ret = nxt_http_pass_find(tmcf->mem_pool, rtcf, &str, pass);
        if (nxt_slow_path(ret != NXT_OK)) {
            return NULL;
        }

    } else {
        pass->handler = nxt_http_pass_var;
    }

    return pass;
}


/* COMPATIBILITY: listener application. */

nxt_http_pass_t *
nxt_http_pass_application(nxt_router_conf_t *rtcf, nxt_str_t *name)
{
    nxt_http_pass_t  *pass;

    pass = nxt_mp_zalloc(rtcf->mem_pool, sizeof(nxt_http_pass_t));
    if (nxt_slow_path(pass == NULL)) {
        return NULL;
    }

    if (nxt_router_application_init(rtcf, name, NULL, pass) != NXT_OK) {
        return NULL;
    }

    return pass;
}


static void
nxt_http_pass_var(nxt_task_t *task, nxt_http_request_t *r, nxt_http_pass_t *pass)
{
    nxt_int_t          ret;
    nxt_str_t          value;
    nxt_http_pass_t    *resolved;
    nxt_router_conf_t  *rtcf;

    rtcf = r->conf->socket_conf->router_conf;

    ret = nxt_tstr_query_init(&r->tstr_query, rtcf->tstr_state, &r->tstr_cache,
                              r, r->mem_pool);
    if (nxt_slow_path(ret != NXT_OK)) {
        goto fail;
    }

    ret = nxt_tstr_query(task, r->tstr_query, pass->u.tstr, &value);
    if (nxt_slow_path(ret != NXT_OK)) {
        goto fail;
    }

    nxt_debug(task, "http pass lookup: %V", &value);

    resolved = nxt_mp_zalloc(r->mem_pool, sizeof(nxt_http_pass_t));
    if (nxt_slow_path(resolved == NULL)) {
        goto fail;
    }

    ret = nxt_http_pass_find(r->mem_pool, rtcf, &value, resolved);
    if (ret == NXT_DECLINED) {
        nxt_http_request_error(task, r, NXT_HTTP_NOT_FOUND);
        return;
    }

    if (nxt_slow_path(ret != NXT_OK)) {
        goto fail;
    }

    resolved->handler(task, r, resolved);
    return;

fail:

    nxt_http_request_error(task, r, NXT_HTTP_INTERNAL_SERVER_ERROR);
}


static nxt_int_t
nxt_http_pass_find(nxt_mp_t *mp, nxt_router_conf_t *rtcf, nxt_str_t *value,
    nxt_http_pass_t *pass)
{
    nxt_int_t  ret;
    nxt_str_t  segments[3];

    ret = nxt_http_pass_segments(mp, value, segments, 3);
    if (nxt_slow_path(ret != NXT_OK)) {
        return ret;
    }

    if (!nxt_str_eq(&segments[0], "applications", 12)
        || segments[1].length == 0)
    {
        return NXT_DECLINED;
    }

    return nxt_router_application_init(rtcf, &segments[1], &segments[2], pass);
}


nxt_int_t
nxt_http_pass_segments(nxt_mp_t *mp, nxt_str_t *pass, nxt_str_t *segments,
    nxt_uint_t n)
{
    u_char     *p;
    nxt_str_t  rest;

    if (nxt_slow_path(nxt_str_dup(mp, &rest, pass) == NULL)) {
        return NXT_ERROR;
    }

    nxt_memzero(segments, n * sizeof(nxt_str_t));

    do {
        p = nxt_memchr(rest.start, '/', rest.length);

        if (p != NULL) {
            n--;

            if (n == 0) {
                return NXT_DECLINED;
            }

            segments->length = p - rest.start;
            segments->start = rest.start;

            rest.length -= segments->length + 1;
            rest.start = p + 1;

        } else {
            n = 0;
            *segments = rest;
        }

        if (segments->length == 0) {
            return NXT_DECLINED;
        }

        p = nxt_decode_uri(segments->start, segments->start, segments->length);
        if (p == NULL) {
            return NXT_DECLINED;
        }

        segments->length = p - segments->start;
        segments++;

    } while (n);

    return NXT_OK;
}
