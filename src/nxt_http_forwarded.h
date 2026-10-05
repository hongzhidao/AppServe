
/*
 * Copyright (C) Hong Zhi Dao
 */

#ifndef _NXT_HTTP_FORWARDED_H_INCLUDED_
#define _NXT_HTTP_FORWARDED_H_INCLUDED_


#include <nxt_http_addr.h>


nxt_int_t nxt_http_forwarded_trusted_parse(nxt_mp_t *mp,
    nxt_http_addr_pattern_t *pattern, nxt_conf_value_t *value);
nxt_int_t nxt_http_forwarded(nxt_http_request_t *r,
    nxt_http_addr_rule_t *trusted);


#endif /* _NXT_HTTP_FORWARDED_H_INCLUDED_ */
