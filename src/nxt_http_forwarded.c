
/*
 * Copyright (C) Hong Zhi Dao
 */

#include <nxt_router.h>
#include <nxt_http.h>
#include <nxt_http_forwarded.h>
#include <arpa/inet.h>


typedef struct {
    nxt_str_t   text;
    nxt_bool_t  escaped;
} nxt_http_forwarded_value_t;


static nxt_int_t nxt_http_forwarded_ip(nxt_str_t *value, nxt_sockaddr_t *sa);
static nxt_bool_t nxt_http_forwarded_trusted_match(nxt_http_addr_rule_t *trusted,
    nxt_sockaddr_t *sa);
static nxt_int_t nxt_http_forwarded_split(nxt_http_field_t *field,
    nxt_array_t *elements);
static nxt_int_t nxt_http_forwarded_add(nxt_array_t *array, nxt_str_t **value);
static nxt_int_t nxt_http_forwarded_element(nxt_mp_t *mp, nxt_str_t *element,
    nxt_array_t *names, nxt_sockaddr_t *sa, nxt_int_t *scheme);
static nxt_int_t nxt_http_forwarded_value(u_char **pos, u_char *end,
    nxt_http_forwarded_value_t *value);
static nxt_int_t nxt_http_forwarded_decode(nxt_mp_t *mp,
    nxt_http_forwarded_value_t *value);
static nxt_int_t nxt_http_forwarded_node(nxt_str_t *value, nxt_sockaddr_t *sa);
static nxt_bool_t nxt_http_forwarded_token(u_char c);
static nxt_bool_t nxt_http_forwarded_obfuscated(u_char *start, u_char *end);
static int nxt_http_forwarded_name_compare(const void *one, const void *two);


nxt_int_t
nxt_http_forwarded_trusted_parse(nxt_mp_t *mp, nxt_http_addr_pattern_t *pattern,
    nxt_conf_value_t *value)
{
    u_char          *slash;
    nxt_str_t       addr;
    nxt_sockaddr_t  sa;

    if (nxt_conf_type(value) != NXT_CONF_STRING) {
        return NXT_ADDR_PATTERN_CV_TYPE_ERROR;
    }

    nxt_conf_get_string(value, &addr);
    slash = nxt_memchr(addr.start, '/', addr.length);

    if (slash != NULL) {
        addr.length = slash - addr.start;
    }

    if (nxt_http_forwarded_ip(&addr, &sa) != NXT_OK) {
        return NXT_ADDR_PATTERN_FORMAT_ERROR;
    }

    return nxt_http_addr_pattern_parse(mp, pattern, value);
}


static nxt_int_t
nxt_http_forwarded_ip(nxt_str_t *value, nxt_sockaddr_t *sa)
{
    char  text[INET6_ADDRSTRLEN];

    if (value->length == 0 || value->length >= sizeof(text)
        || nxt_memchr(value->start, '\0', value->length) != NULL)
    {
        return NXT_DECLINED;
    }

    nxt_memcpy(text, value->start, value->length);
    text[value->length] = '\0';
    nxt_memzero(sa, sizeof(nxt_sockaddr_t));

    if (inet_pton(AF_INET, text, &sa->u.sockaddr_in.sin_addr) == 1) {
        sa->u.sockaddr_in.sin_family = AF_INET;
        sa->socklen = sizeof(struct sockaddr_in);
        return NXT_OK;
    }

#if (NXT_INET6)
    if (inet_pton(AF_INET6, text, &sa->u.sockaddr_in6.sin6_addr) == 1) {
        sa->u.sockaddr_in6.sin6_family = AF_INET6;
        sa->socklen = sizeof(struct sockaddr_in6);
        return NXT_OK;
    }
#endif

    return NXT_DECLINED;
}


static nxt_bool_t
nxt_http_forwarded_trusted_match(nxt_http_addr_rule_t *trusted,
    nxt_sockaddr_t *sa)
{
#if (NXT_INET6)
    nxt_sockaddr_t  v4;
#endif

    if (nxt_http_addr_rule_match(trusted, sa)) {
        return 1;
    }

#if (NXT_INET6)
    if (sa->u.sockaddr.sa_family == AF_INET6
        && IN6_IS_ADDR_V4MAPPED(&sa->u.sockaddr_in6.sin6_addr))
    {
        nxt_memzero(&v4, sizeof(nxt_sockaddr_t));
        v4.u.sockaddr_in.sin_family = AF_INET;
        v4.u.sockaddr_in.sin_port = sa->u.sockaddr_in6.sin6_port;
        nxt_memcpy(&v4.u.sockaddr_in.sin_addr,
                   &sa->u.sockaddr_in6.sin6_addr.s6_addr[12], 4);

        return nxt_http_addr_rule_match(trusted, &v4);
    }
#endif

    return 0;
}


nxt_int_t
nxt_http_forwarded(nxt_http_request_t *r, nxt_http_addr_rule_t *trusted)
{
    size_t            length;
    uint32_t          i;
    nxt_int_t         ret, scheme;
    nxt_str_t         *element;
    nxt_array_t       *elements, *names;
    nxt_sockaddr_t    sa, *remote;
    nxt_http_field_t  *field;

    if (!nxt_http_forwarded_trusted_match(trusted, r->peer)) {
        return NXT_OK;
    }

    elements = NULL;

    nxt_list_each(field, r->fields) {
        if (field->name_length != nxt_length("Forwarded")
            || nxt_memcasecmp(field->name, "Forwarded",
                              nxt_length("Forwarded")) != 0)
        {
            continue;
        }

        if (elements == NULL) {
            elements = nxt_array_create(r->mem_pool, 4, sizeof(nxt_str_t));
            if (nxt_slow_path(elements == NULL)) {
                return NXT_ERROR;
            }
        }

        ret = nxt_http_forwarded_split(field, elements);
        if (ret != NXT_OK) {
            return (ret == NXT_ERROR) ? NXT_ERROR : NXT_OK;
        }
    } nxt_list_loop;

    if (elements == NULL || elements->nelts == 0) {
        return NXT_OK;
    }

    names = nxt_array_create(r->mem_pool, 4, sizeof(nxt_str_t));
    if (nxt_slow_path(names == NULL)) {
        return NXT_ERROR;
    }

    element = elements->elts;
    i = elements->nelts;
    remote = NULL;
    scheme = -1;

    while (i != 0) {
        ret = nxt_http_forwarded_element(r->mem_pool, &element[--i], names,
                                          &sa, &scheme);
        if (ret == NXT_ERROR) {
            return NXT_ERROR;
        }

        if (ret == NXT_DECLINED) {
            /* Do not commit a partially parsed chain. */
            return NXT_OK;
        }

        if (ret == NXT_DONE) {
            /* A missing, unknown or obfuscated node ends the chain. */
            remote = NULL;
            break;
        }

        if (i == 0 || !nxt_http_forwarded_trusted_match(trusted, &sa)) {
            length = (sa.u.sockaddr.sa_family == AF_INET)
                     ? NXT_INET_ADDR_STR_LEN : NXT_INET6_ADDR_STR_LEN;

            remote = nxt_sockaddr_create(r->mem_pool, &sa.u.sockaddr,
                                          sa.socklen, length);
            if (nxt_slow_path(remote == NULL)) {
                return NXT_ERROR;
            }

            nxt_sockaddr_text(remote);
            break;
        }
    }

    if (remote != NULL) {
        r->remote = remote;
    }

    if (scheme >= 0) {
        r->https = scheme;
    }

    return NXT_OK;
}


static nxt_int_t
nxt_http_forwarded_split(nxt_http_field_t *field, nxt_array_t *elements)
{
    u_char      *p, *start, *end;
    nxt_int_t   ret;
    nxt_str_t   *element;
    nxt_bool_t  quoted;

    start = field->value;
    end = start + field->value_length;
    quoted = 0;

    for (p = start; p < end; p++) {
        if (quoted && *p == '\\') {
            if (++p == end) {
                return NXT_DECLINED;
            }

        } else if (*p == '"') {
            quoted = !quoted;

        } else if (!quoted && *p == ',') {
            ret = nxt_http_forwarded_add(elements, &element);
            if (ret != NXT_OK) {
                return ret;
            }

            element->start = start;
            element->length = p - start;
            start = p + 1;
        }
    }

    if (quoted) {
        return NXT_DECLINED;
    }

    ret = nxt_http_forwarded_add(elements, &element);
    if (ret != NXT_OK) {
        return ret;
    }

    element->start = start;
    element->length = end - start;

    return NXT_OK;
}


static nxt_int_t
nxt_http_forwarded_add(nxt_array_t *array, nxt_str_t **value)
{
    /* Leave room for growth of nxt_array_t's 16-bit capacity. */
    if (array->nelts >= UINT16_MAX / 2) {
        return NXT_DECLINED;
    }

    *value = nxt_array_add(array);
    if (nxt_slow_path(*value == NULL)) {
        return NXT_ERROR;
    }

    return NXT_OK;
}


static nxt_int_t
nxt_http_forwarded_element(nxt_mp_t *mp, nxt_str_t *element, nxt_array_t *names,
    nxt_sockaddr_t *sa, nxt_int_t *scheme)
{
    u_char                      *p, *end;
    uint32_t                    i;
    nxt_int_t                   ret;
    nxt_str_t                   name, *stored;
    nxt_http_forwarded_value_t  value, node, proto;

    p = element->start;
    end = p + element->length;
    names->nelts = 0;
    nxt_memzero(&node, sizeof(node));
    nxt_memzero(&proto, sizeof(proto));
    *scheme = -1;

    for ( ;; ) {
        while (p < end && (*p == ' ' || *p == '\t')) {
            p++;
        }

        if (p == end) {
            break;
        }

        if (*p == ';') {
            p++;
            continue;
        }

        name.start = p;

        while (p < end && nxt_http_forwarded_token(*p)) {
            p++;
        }

        name.length = p - name.start;

        if (name.length == 0 || p == end || *p++ != '=') {
            return NXT_DECLINED;
        }

        ret = nxt_http_forwarded_value(&p, end, &value);
        if (ret != NXT_OK) {
            return ret;
        }

        ret = nxt_http_forwarded_add(names, &stored);
        if (ret != NXT_OK) {
            return ret;
        }

        *stored = name;

        if (name.length == 3 && nxt_memcasecmp(name.start, "for", 3) == 0) {
            node = value;

        } else if (name.length == 5
                   && nxt_memcasecmp(name.start, "proto", 5) == 0)
        {
            proto = value;
        }

        while (p < end && (*p == ' ' || *p == '\t')) {
            p++;
        }

        if (p == end) {
            break;
        }

        if (*p++ != ';') {
            return NXT_DECLINED;
        }
    }

    if (names->nelts == 0) {
        return NXT_DECLINED;
    }

    stored = names->elts;
    nxt_qsort(stored, names->nelts, sizeof(nxt_str_t),
              nxt_http_forwarded_name_compare);

    for (i = 1; i < names->nelts; i++) {
        if (nxt_http_forwarded_name_compare(&stored[i - 1], &stored[i]) == 0) {
            return NXT_DECLINED;
        }
    }

    ret = nxt_http_forwarded_decode(mp, &proto);
    if (ret != NXT_OK) {
        return ret;
    }

    if (proto.text.length == 4
        && nxt_memcasecmp(proto.text.start, "http", 4) == 0)
    {
        *scheme = 0;

    } else if (proto.text.length == 5
               && nxt_memcasecmp(proto.text.start, "https", 5) == 0)
    {
        *scheme = 1;
    }

    if (node.text.start == NULL) {
        return NXT_DONE;
    }

    ret = nxt_http_forwarded_decode(mp, &node);
    if (ret != NXT_OK) {
        return ret;
    }

    return nxt_http_forwarded_node(&node.text, sa);
}


static nxt_int_t
nxt_http_forwarded_value(u_char **pos, u_char *end,
    nxt_http_forwarded_value_t *value)
{
    u_char  c, *p, *start;

    p = *pos;
    value->escaped = 0;

    if (p == end) {
        return NXT_DECLINED;
    }

    if (*p != '"') {
        start = p;

        while (p < end && nxt_http_forwarded_token(*p)) {
            p++;
        }

        if (p == start) {
            return NXT_DECLINED;
        }

        value->text.start = start;
        value->text.length = p - start;
        *pos = p;
        return NXT_OK;
    }

    start = ++p;

    while (p < end) {
        c = *p++;

        if (c == '"') {
            value->text.start = start;
            value->text.length = p - start - 1;
            *pos = p;
            return NXT_OK;
        }

        if (c == '\\') {
            if (p == end) {
                return NXT_DECLINED;
            }

            value->escaped = 1;
            c = *p++;
        }

        if ((c < 0x20 && c != '\t') || c == 0x7F) {
            return NXT_DECLINED;
        }
    }

    return NXT_DECLINED;
}


static nxt_int_t
nxt_http_forwarded_decode(nxt_mp_t *mp, nxt_http_forwarded_value_t *value)
{
    u_char  *p, *end, *out, *start;

    if (!value->escaped) {
        return NXT_OK;
    }

    start = nxt_mp_nget(mp, value->text.length);
    if (nxt_slow_path(start == NULL)) {
        return NXT_ERROR;
    }

    p = value->text.start;
    end = p + value->text.length;
    out = start;

    while (p < end) {
        if (*p == '\\') {
            p++;
        }

        *out++ = *p++;
    }

    value->text.start = start;
    value->text.length = out - start;

    return NXT_OK;
}


static nxt_int_t
nxt_http_forwarded_node(nxt_str_t *value, nxt_sockaddr_t *sa)
{
    u_char      *p, *end;
    nxt_int_t   ret, port;
    nxt_str_t   addr;
    nxt_bool_t  opaque, ipv6;

    addr = *value;
    end = addr.start + addr.length;
    opaque = 0;
    ipv6 = 0;

    if (addr.length == 0) {
        return NXT_DECLINED;
    }

    if (*addr.start == '[') {
        ipv6 = 1;
        addr.start++;
        p = nxt_memchr(addr.start, ']', end - addr.start);
        if (p == NULL) {
            return NXT_DECLINED;
        }

        addr.length = p - addr.start;
        p++;

    } else {
        p = nxt_memchr(addr.start, ':', addr.length);
        if (p == NULL) {
            p = end;
        }

        addr.length = p - addr.start;

        if (addr.length == 7
            && nxt_memcasecmp(addr.start, "unknown", 7) == 0)
        {
            opaque = 1;

        } else if (addr.length > 1 && *addr.start == '_') {
            opaque = 1;

            if (!nxt_http_forwarded_obfuscated(addr.start, p)) {
                return NXT_DECLINED;
            }
        }
    }

    port = 0;

    if (p < end) {
        if (*p++ != ':' || p == end) {
            return NXT_DECLINED;
        }

        if (*p == '_') {
            if (!nxt_http_forwarded_obfuscated(p, end)) {
                return NXT_DECLINED;
            }

        } else {
            if (end - p > 5) {
                return NXT_DECLINED;
            }

            port = nxt_int_parse(p, end - p);
            if (port < 0 || port > 65535) {
                return NXT_DECLINED;
            }
        }
    }

    if (opaque) {
        return NXT_DONE;
    }

    ret = nxt_http_forwarded_ip(&addr, sa);
    if (ret != NXT_OK) {
        return ret;
    }

    if (!ipv6 && sa->u.sockaddr.sa_family == AF_INET) {
        if (sa->u.sockaddr_in.sin_addr.s_addr == INADDR_ANY) {
            return NXT_DECLINED;
        }

        sa->u.sockaddr_in.sin_port = htons(port);
        return NXT_OK;
    }

#if (NXT_INET6)
    if (ipv6 && sa->u.sockaddr.sa_family == AF_INET6) {
        if (IN6_IS_ADDR_UNSPECIFIED(&sa->u.sockaddr_in6.sin6_addr)) {
            return NXT_DECLINED;
        }

        sa->u.sockaddr_in6.sin6_port = htons(port);
        return NXT_OK;
    }
#endif

    return NXT_DECLINED;
}


static nxt_bool_t
nxt_http_forwarded_token(u_char c)
{
    return ((c >= '0' && c <= '9')
            || (nxt_lowcase(c) >= 'a' && nxt_lowcase(c) <= 'z')
            || nxt_memchr("!#$%&'*+-.^_`|~", c,
                          nxt_length("!#$%&'*+-.^_`|~")) != NULL);
}


static int
nxt_http_forwarded_name_compare(const void *one, const void *two)
{
    nxt_int_t        ret;
    const nxt_str_t  *a, *b;

    a = one;
    b = two;
    ret = nxt_memcasecmp(a->start, b->start, nxt_min(a->length, b->length));

    if (ret != 0) {
        return ret;
    }

    return (a->length > b->length) - (a->length < b->length);
}


static nxt_bool_t
nxt_http_forwarded_obfuscated(u_char *start, u_char *end)
{
    u_char  c;

    if (end - start < 2 || *start++ != '_') {
        return 0;
    }

    while (start < end) {
        c = *start++;

        if (!((c >= '0' && c <= '9')
              || (nxt_lowcase(c) >= 'a' && nxt_lowcase(c) <= 'z')
              || c == '.' || c == '_' || c == '-'))
        {
            return 0;
        }
    }

    return 1;
}
