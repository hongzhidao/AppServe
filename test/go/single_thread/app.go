package main

/*
#include <pthread.h>
#include <stdint.h>

static uintptr_t current_thread(void) {
    return (uintptr_t) pthread_self();
}
*/
import "C"

import (
	"fmt"
	"io"
	"io/ioutil"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync/atomic"
	"time"

	"unit.nginx.org/go"
)

var active int32

func handler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("X-Active", strconv.Itoa(int(atomic.AddInt32(&active, 1))))
	defer atomic.AddInt32(&active, -1)
	w.Header().Set("X-Pid", strconv.Itoa(os.Getpid()))
	w.Header().Set("X-Thread", fmt.Sprint(C.current_thread()))

	if r.URL.Path == "/delay" {
		time.Sleep(100 * time.Millisecond)
	}

	if r.URL.Path == "/large" {
		size, _ := strconv.Atoi(r.URL.Query().Get("size"))
		w.Header().Set("Content-Length", strconv.Itoa(size))
		io.WriteString(w, strings.Repeat("x", size))
		return
	}

	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Length", strconv.Itoa(len(body)))
	w.Write(body)
}

func main() {
	unit.ListenAndServe(":8080", http.HandlerFunc(handler))
}
