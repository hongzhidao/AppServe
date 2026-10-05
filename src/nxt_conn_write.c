
/*
 * Copyright (C) Igor Sysoev
 * Copyright (C) NGINX, Inc.
 */

#include <nxt_main.h>


static void nxt_conn_write_timer_handler(nxt_task_t *task, void *obj,
    void *data);


void
nxt_conn_io_write(nxt_task_t *task, void *obj, void *data)
{
    ssize_t             ret;
    nxt_buf_t           *b;
    nxt_conn_t          *c;
    nxt_sendbuf_t       sb;
    nxt_event_engine_t  *engine;

    c = obj;

    nxt_debug(task, "conn write fd:%d er:%d bl:%d",
              c->socket.fd, c->socket.error, c->block_write);

    if (c->socket.error != 0 || c->block_write) {
        goto error;
    }

    if (!c->socket.write_ready || c->write == NULL) {
        return;
    }

    engine = task->thread->engine;

    c->socket.write_handler = nxt_conn_io_write;
    c->socket.error_handler = c->write_state->error_handler;

    b = c->write;

    sb.socket = c->socket.fd;
    sb.error = 0;
    sb.sent = 0;
    sb.size = 0;
    sb.buf = b;
    sb.limit = 10 * 1024 * 1024;
    sb.ready = 1;
    sb.sync = 0;

    do {
        ret = c->io->sendbuf(task, &sb);

        c->socket.write_ready = sb.ready;
        c->socket.error = sb.error;

        if (ret < 0) {
            /* ret == NXT_AGAIN || ret == NXT_ERROR. */
            break;
        }

        sb.sent += ret;
        sb.limit -= ret;

        b = nxt_sendbuf_update(b, ret);

        if (b == NULL) {
            nxt_fd_event_block_write(engine, &c->socket);
            break;
        }

        sb.buf = b;

        if (!c->socket.write_ready) {
            ret = NXT_AGAIN;
            break;
        }

    } while (sb.limit != 0);

    nxt_debug(task, "event conn: %z sent:%O", ret, sb.sent);

    if (sb.sent != 0) {
        if (c->write_state->timer_autoreset) {
            nxt_timer_disable(engine, &c->write_timer);
        }
    }

    if (ret != NXT_ERROR) {

        if (sb.limit == 0) {
            /*
             * Postpone writing until next event poll to allow to
             * process other received events and to get new events.
             */
            c->write_timer.handler = nxt_conn_write_timer_handler;
            nxt_timer_add(engine, &c->write_timer, 0);

        } else if (ret == NXT_AGAIN) {
            nxt_conn_timer(engine, c, c->write_state, &c->write_timer);

            if (nxt_fd_event_is_disabled(c->socket.write)) {
                nxt_fd_event_enable_write(engine, &c->socket);
            }
        }
    }

    if (ret == 0 || sb.sent != 0) {
        /*
         * ret == 0 means a sync buffer was processed.
         * ret == NXT_ERROR is ignored here if some data was sent,
         * the error will be handled on the next nxt_conn_write() call.
         */
        c->sent += sb.sent;
        nxt_work_queue_add(c->write_work_queue, c->write_state->ready_handler,
                           task, c, data);
        return;
    }

    if (ret != NXT_ERROR) {
        return;
    }

    nxt_fd_event_block_write(engine, &c->socket);

error:

    nxt_work_queue_add(c->write_work_queue, c->write_state->error_handler,
                       task, c, data);
}


static void
nxt_conn_write_timer_handler(nxt_task_t *task, void *obj, void *data)
{
    nxt_conn_t   *c;
    nxt_timer_t  *timer;

    timer = obj;

    nxt_debug(task, "conn write timer");

    c = nxt_write_timer_conn(timer);

    c->io->write(task, c, c->socket.data);
}


ssize_t
nxt_conn_io_sendbuf(nxt_task_t *task, nxt_sendbuf_t *sb)
{
    nxt_uint_t    niov;
    struct iovec  iov[NXT_IOBUF_MAX];

    niov = nxt_sendbuf_mem_coalesce0(task, sb, iov, NXT_IOBUF_MAX);

    if (niov == 0) {
        if (nxt_slow_path(sb->buf != NULL && nxt_buf_is_file(sb->buf))) {
            sb->error = NXT_EINVAL;
            nxt_alert(task, "file buffer in connection write");

            return NXT_ERROR;
        }

        return 0;
    }

    return nxt_conn_io_writev(task, sb, iov, niov);
}


ssize_t
nxt_conn_io_writev(nxt_task_t *task, nxt_sendbuf_t *sb, struct iovec *iov,
    nxt_uint_t niov)
{
    ssize_t    n;
    nxt_err_t  err;

    if (niov == 1) {
        /* Disposal of surplus kernel iovec copy-in operation. */
        return nxt_conn_io_send(task, sb, iov[0].iov_base, iov[0].iov_len);
    }

    for ( ;; ) {
        n = writev(sb->socket, iov, niov);

        err = (n == -1) ? nxt_socket_errno : 0;

        nxt_debug(task, "writev(%d, %ui): %z", sb->socket, niov, n);

        if (n > 0) {
            return n;
        }

        /* n == -1 */

        switch (err) {

        case NXT_EAGAIN:
            sb->ready = 0;
            nxt_debug(task, "writev() %E", err);

            return NXT_AGAIN;

        case NXT_EINTR:
            nxt_debug(task, "writev() %E", err);
            continue;

        default:
            sb->error = err;
            nxt_log(task, nxt_socket_error_level(err),
                    "writev(%d, %ui) failed %E", sb->socket, niov, err);

            return NXT_ERROR;
        }
    }
}


ssize_t
nxt_conn_io_send(nxt_task_t *task, nxt_sendbuf_t *sb, void *buf, size_t size)
{
    ssize_t    n;
    nxt_err_t  err;

    for ( ;; ) {
        n = send(sb->socket, buf, size, 0);

        err = (n == -1) ? nxt_socket_errno : 0;

        nxt_debug(task, "send(%d, %p, %uz): %z", sb->socket, buf, size, n);

        if (n > 0) {
            return n;
        }

        /* n == -1 */

        switch (err) {

        case NXT_EAGAIN:
            sb->ready = 0;
            nxt_debug(task, "send() %E", err);

            return NXT_AGAIN;

        case NXT_EINTR:
            nxt_debug(task, "send() %E", err);
            continue;

        default:
            sb->error = err;
            nxt_log(task, nxt_socket_error_level(err),
                    "send(%d, %p, %uz) failed %E", sb->socket, buf, size, err);

            return NXT_ERROR;
        }
    }
}
