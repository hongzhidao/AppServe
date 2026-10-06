
/*
 * Copyright (C) Zhidao HONG
 */

#include <nxt_main.h>
#include "nxt_tests.h"


typedef enum {
    NXT_THREAD_TEST_RETURN,
    NXT_THREAD_TEST_EXIT,
    NXT_THREAD_TEST_PTHREAD_EXIT,
    NXT_THREAD_TEST_CANCEL,
} nxt_thread_test_mode_t;


typedef struct {
    nxt_thread_link_t        *link;
    nxt_event_engine_t       *engine;
    nxt_sem_t                started;
    int                      gate[2];
    nxt_thread_test_mode_t   mode;
    nxt_int_t                result;
    nxt_uint_t               exits;
} nxt_thread_test_ctx_t;


static u_char *nxt_thread_test_time_string(u_char *buf, nxt_realtime_t *now,
    struct tm *tm, size_t size, const char *format);
static void nxt_thread_test_start(nxt_thread_link_t *link);
static void nxt_thread_test_signal(nxt_event_engine_t *engine,
    nxt_uint_t signo);
static void nxt_thread_test_exit(nxt_task_t *task, void *obj, void *data);


static nxt_time_string_t  nxt_thread_test_time = {
    .handler = nxt_thread_test_time_string,
    .size = 1,
    .timezone = NXT_THREAD_TIME_GMT,
};


static u_char *
nxt_thread_test_time_string(u_char *buf, nxt_realtime_t *now, struct tm *tm,
    size_t size, const char *format)
{
    *buf++ = 'x';
    return buf;
}


static void
nxt_thread_test_start(nxt_thread_link_t *link)
{
    u_char                 buf[1];
    nxt_thread_t           *thr;
    nxt_thread_test_ctx_t  *ctx;

    thr = nxt_thread();
    ctx = link->work.data;

    ctx->result = (link == ctx->link && thr->link == link
                   && link->engine == ctx->engine)
                  ? NXT_OK : NXT_ERROR;

    if (nxt_thread_time_string(thr, &nxt_thread_test_time, buf) != buf + 1
        || buf[0] != 'x' || thr->time.strings == NULL)
    {
        ctx->result = NXT_ERROR;
    }

    (void) nxt_sem_post(&ctx->started);

    /* read() provides a deterministic cancellation point. */
    if (read(ctx->gate[0], buf, 1) != 1) {
        ctx->result = NXT_ERROR;
    }

    if (link != ctx->link || thr->link != link) {
        ctx->result = NXT_ERROR;
    }

    if (ctx->mode == NXT_THREAD_TEST_EXIT) {
        nxt_thread_exit(thr);

    } else if (ctx->mode == NXT_THREAD_TEST_PTHREAD_EXIT) {
        pthread_exit(NULL);
    }
}


static void
nxt_thread_test_signal(nxt_event_engine_t *engine, nxt_uint_t signo)
{
    /* The test drains the posted exit work after joining the thread. */
}


static void
nxt_thread_test_exit(nxt_task_t *task, void *obj, void *data)
{
    nxt_thread_test_ctx_t  *ctx;

    ctx = data;
    ctx->exits++;

    if (task != &ctx->engine->task || ctx->link->work.obj != obj) {
        ctx->result = NXT_ERROR;
    }

    nxt_free(ctx->link);
}


nxt_int_t
nxt_thread_test(nxt_thread_t *thr)
{
    void                   *retval, *obj, *data;
    nxt_int_t              ret;
    nxt_uint_t             handler, mode;
    nxt_task_t             *task;
    nxt_thread_link_t      *link;
    nxt_event_engine_t     engine;
    nxt_thread_handle_t    handle;
    nxt_work_handler_t     exit;
    nxt_thread_test_ctx_t  ctx;

    nxt_memzero(&engine, sizeof(engine));
    engine.task.thread = thr;
    engine.task.log = thr->log;
    engine.event.signal = nxt_thread_test_signal;

    for (handler = 0; handler < 2; handler++) {
        for (mode = NXT_THREAD_TEST_RETURN; mode <= NXT_THREAD_TEST_CANCEL;
             mode++)
        {
            nxt_memzero(&ctx, sizeof(ctx));
            ctx.engine = &engine;
            ctx.mode = mode;

            if (nxt_sem_init(&ctx.started, 0) != NXT_OK) {
                return NXT_ERROR;
            }

            if (pipe(ctx.gate) != 0) {
                nxt_sem_destroy(&ctx.started);
                return NXT_ERROR;
            }

            link = nxt_zalloc(sizeof(nxt_thread_link_t));
            if (link == NULL) {
                close(ctx.gate[0]);
                close(ctx.gate[1]);
                nxt_sem_destroy(&ctx.started);
                return NXT_ERROR;
            }

            ctx.link = link;
            link->start = nxt_thread_test_start;
            link->engine = &engine;
            link->work.data = &ctx;

            if (handler) {
                link->work.handler = nxt_thread_test_exit;
                link->work.task = &engine.task;
            }

            ret = nxt_thread_create(&handle, link);
            if (ret == NXT_OK) {
                ret = nxt_sem_wait(&ctx.started, NXT_INFINITE_NSEC);

                if (mode == NXT_THREAD_TEST_CANCEL) {
                    nxt_thread_cancel(handle);

                } else if (write(ctx.gate[1], "x", 1) != 1) {
                    ret = NXT_ERROR;
                    nxt_thread_cancel(handle);
                }

                if (pthread_join(handle, &retval) != 0) {
                    ret = NXT_ERROR;

                } else if (retval != ((mode == NXT_THREAD_TEST_CANCEL)
                                      ? PTHREAD_CANCELED : NULL))
                {
                    ret = NXT_ERROR;
                }

                exit = nxt_locked_work_queue_pop(&engine.locked_work_queue,
                                                 &task, &obj, &data);
                if (handler) {
                    if (exit != nxt_thread_test_exit
                        || !nxt_thread_handle_equal(
                                (nxt_thread_handle_t) (uintptr_t) obj, handle))
                    {
                        ret = NXT_ERROR;
                    }
                } else if (exit != NULL) {
                    ret = NXT_ERROR;
                }

                if (exit != NULL) {
                    exit(task, obj, data);
                }

                if (ctx.result != NXT_OK || ctx.exits != handler
                    || nxt_locked_work_queue_pop(&engine.locked_work_queue,
                                                  &task, &obj, &data) != NULL)
                {
                    ret = NXT_ERROR;
                }
            }

            close(ctx.gate[0]);
            close(ctx.gate[1]);
            nxt_sem_destroy(&ctx.started);

            if (ret != NXT_OK) {
                nxt_log_alert(thr->log, "thread test failed: mode %ui, "
                              "exit handler %ui", mode, handler);
                return NXT_ERROR;
            }
        }
    }

    nxt_log_error(NXT_LOG_NOTICE, thr->log, "thread test passed");
    return NXT_OK;
}
