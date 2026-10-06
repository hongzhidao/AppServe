/*
 * Copyright (C) Max Romanov
 * Copyright (C) NGINX, Inc.
 */

package unit

/*
#include "nxt_cgo_lib.h"
*/
import "C"

import (
	"errors"
	"net/http"
	"unsafe"
)

type response struct {
	header      http.Header
	header_sent bool
	c_req       *C.nxt_unit_request_info_t
	err         error
}

func (r *response) Header() http.Header {
	return r.header
}

func (r *response) Write(p []byte) (n int, err error) {
	if !r.header_sent {
		r.WriteHeader(http.StatusOK)
	}

	if r.err != nil {
		return 0, r.err
	}

	if len(p) == 0 {
		return 0, nil
	}

	res := C.nxt_cgo_response_write(r.c_req, unsafe.Pointer(&p[0]), C.size_t(len(p)))
	if res < 0 {
		r.err = errors.New("unit: failed to write response body")
		return 0, r.err
	}

	return int(res), nil
}

func (r *response) WriteHeader(code int) {
	if r.header_sent {
		nxt_go_warn("multiple response.WriteHeader calls")
		return
	}
	r.header_sent = true

	// Set a default Content-Type
	if _, hasType := r.header["Content-Type"]; !hasType {
		r.header.Add("Content-Type", "text/html; charset=utf-8")
	}

	fields := 0
	fields_size := 0

	for k, vv := range r.header {
		for _, v := range vv {
			fields++
			fields_size += len(k) + len(v)
		}
	}

	if C.nxt_unit_response_init(r.c_req, C.uint16_t(code), C.uint32_t(fields),
		C.uint32_t(fields_size)) != C.NXT_UNIT_OK {
		r.err = errors.New("unit: failed to initialize response")
		return
	}

	for k, vv := range r.header {
		for _, v := range vv {
			if C.nxt_unit_response_add_field(r.c_req, str_ref(k), C.uint8_t(len(k)),
				str_ref(v), C.uint32_t(len(v))) != C.NXT_UNIT_OK {
				r.err = errors.New("unit: failed to add response header")
				return
			}
		}
	}

	if C.nxt_unit_response_send(r.c_req) != C.NXT_UNIT_OK {
		r.err = errors.New("unit: failed to send response headers")
	}
}

func (r *response) Flush() {
	if !r.header_sent {
		r.WriteHeader(http.StatusOK)
	}
}
