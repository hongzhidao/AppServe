
/*
 * Copyright (C) Max Romanov
 * Copyright (C) NGINX, Inc.
 */

#include "_cgo_export.h"

#include <nxt_unit.h>
#include <nxt_unit_request.h>


int
nxt_cgo_run(uintptr_t handler)
{
    int              rc;
    nxt_unit_ctx_t   *ctx;
    nxt_unit_init_t  init;

    memset(&init, 0, sizeof(init));

    init.callbacks.request_handler = nxt_go_request_handler;

    init.data = (void *) handler;

    ctx = nxt_unit_init(&init);
    if (ctx == NULL) {
        return NXT_UNIT_ERROR;
    }

    rc = nxt_unit_run(ctx);

    nxt_unit_done(ctx);

    return rc;
}


ssize_t
nxt_cgo_response_write(nxt_unit_request_info_t *req, const void *start,
    size_t len)
{
    return nxt_unit_response_write_nb(req, start, len, len);
}


ssize_t
nxt_cgo_request_read(nxt_unit_request_info_t *req, void *dst, size_t dst_len)
{
    return nxt_unit_request_read(req, dst, dst_len);
}


void
nxt_cgo_warn(const char *msg, uint32_t msg_len)
{
    nxt_unit_warn(NULL, "%.*s", (int) msg_len, (char *) msg);
}


void
nxt_cgo_alert(const char *msg, uint32_t msg_len)
{
    nxt_unit_alert(NULL, "%.*s", (int) msg_len, (char *) msg);
}
