
/*
 * Copyright (C) Igor Sysoev
 * Copyright (C) NGINX, Inc.
 */

#ifndef _NXT_SENDBUF_H_INCLUDED_
#define _NXT_SENDBUF_H_INCLUDED_


/*
 * The sendbuf interface is intended to send a memory buffer chain to a
 * connection.
 *
 * The sendbuf interface sets sb->ready to the appropriate state
 * and returns:
 *
 *   N > 0      if sendbuf sent N bytes.
 *
 *   0          if sendbuf was interrupted (EINTR and so on),
 *              or sendbuf sent previously buffered data,
 *              or single sync buffer has been encountered.
 *              In all these cases sendbuf is ready to continue
 *              operation, unless sb->ready is cleared.
 *
 *   NXT_AGAIN  if sendbuf did not send any bytes.
 *
 *   NXT_ERROR  if there was an error.
 *
 * The sendbuf limit is size_t type.  The limit support is located at the
 * sendbuf level, otherwise an additional limited chain must be created
 * on each sendbuf call.
 */


typedef struct {
    nxt_buf_t     *buf;
    nxt_socket_t  socket;
    nxt_err_t     error;
    nxt_off_t     sent;
    size_t        size;
    size_t        limit;

    uint8_t       ready;   /* 1 bit */
    uint8_t       once;    /* 1 bit */
    uint8_t       sync;    /* 1 bit */
    uint8_t       last;    /* 1 bit */
} nxt_sendbuf_t;


typedef struct {
    nxt_buf_t    *buf;
    nxt_iobuf_t  *iobuf;
    nxt_uint_t   niov;

    uint32_t     nmax;
    uint8_t      sync;   /* 1 bit */
    uint8_t      last;   /* 1 bit */
    uint8_t      limit_reached;
    uint8_t      nmax_reached;

    size_t       size;
    size_t       limit;
} nxt_sendbuf_coalesce_t;


nxt_uint_t nxt_sendbuf_mem_coalesce0(nxt_task_t *task, nxt_sendbuf_t *sb,
    struct iovec *iov, nxt_uint_t niov_max);
nxt_uint_t nxt_sendbuf_mem_coalesce(nxt_task_t *task,
    nxt_sendbuf_coalesce_t *sb);

nxt_buf_t *nxt_sendbuf_update(nxt_buf_t *b, size_t sent);
nxt_buf_t *nxt_sendbuf_completion(nxt_task_t *task, nxt_work_queue_t *wq,
    nxt_buf_t *b);
void nxt_sendbuf_drain(nxt_task_t *task, nxt_work_queue_t *wq, nxt_buf_t *b);


#endif /* _NXT_SENDBUF_H_INCLUDED_ */
