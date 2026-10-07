
/*
 * Copyright (C) NGINX, Inc.
 */

#ifndef _NXT_STATUS_H_INCLUDED_
#define _NXT_STATUS_H_INCLUDED_


typedef struct {
    nxt_str_t         name;
    uint32_t          active_requests;
    uint32_t          max_processes;
    uint32_t          spare_processes;
    uint32_t          busy_processes;
    uint32_t          idle_processes;
} nxt_status_app_t;


typedef struct {
    uint64_t          requests;
    uint64_t          busy_processes;
    uint64_t          idle_processes;

    size_t            apps_count;
    nxt_status_app_t  apps[];
} nxt_status_report_t;


nxt_conf_value_t *nxt_status_get(nxt_status_report_t *report, nxt_mp_t *mp);


#endif /* _NXT_STATUS_H_INCLUDED_ */
