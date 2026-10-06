
/*
 * Copyright (C) Hong Zhi Dao
 */

#include <nxt_main.h>
#include "nxt_tests.h"


nxt_int_t
nxt_murmur_hash_test(nxt_thread_t *thr, nxt_bool_t fixed)
{
    uint32_t    hash;
    nxt_uint_t  i, offset;
    u_char      buf[16] nxt_aligned(8);

    /* MurmurHash2 with seed zero, using little-endian input words. */
    static struct {
        nxt_str_t  input;
        uint32_t   expected;
    } tests[] = {
        { nxt_string(""), 0x00000000 },
        { nxt_string("a"), 0x92685F5E },
        { nxt_string("abc"), 0x13577C9B },
        { nxt_string("abcd"), 0x26873021 },
        { nxt_string("\x00\x00\x00\x80"), 0x26DE7447 },
        { nxt_string("\xFF\xFF\xFF\xFF"), 0x14ACB3DA },
        { nxt_string("\x01\x23\x45\x80"), 0x6C02796D },
        { nxt_string("\x01\x23\x45\x80\xFF"), 0x97C617D3 },
        { nxt_string("\x01\x23\x45\x80\xFF\xFE"), 0x23802071 },
        { nxt_string("\x01\x23\x45\x80\xFF\xFE\xFD"), 0x0BE33277 },
        { nxt_string("\x01\x23\x45\x80\xFF\xFE\xFD\xFC"), 0x6751658F },
        { nxt_string("\x01\x23\x45\x80\xFF\xFE\xFD\xFC\xFB"), 0x6A212A41 },
    };

    for (i = 0; i < nxt_nitems(tests); i++) {
        if (fixed && tests[i].input.length != sizeof(uint32_t)) {
            continue;
        }

        for (offset = 0; offset < 8; offset++) {
            nxt_memcpy(buf + offset, tests[i].input.start,
                       tests[i].input.length);

            if (fixed) {
                hash = nxt_murmur_hash2_uint32(buf + offset);

            } else {
                hash = nxt_murmur_hash2(buf + offset, tests[i].input.length);
            }

            if (hash != tests[i].expected) {
                nxt_log_alert(thr->log,
                              "murmur hash test %ui offset %ui failed: "
                              "0x%08XD, expected 0x%08XD",
                              i, offset, hash, tests[i].expected);
                return NXT_ERROR;
            }
        }
    }

    nxt_log_error(NXT_LOG_NOTICE, thr->log, "murmur hash%s test passed",
                  fixed ? " uint32" : "");

    return NXT_OK;
}
