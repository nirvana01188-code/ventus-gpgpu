#pragma once

/*
 * Celviz GPGPU runtime proxy API surface.
 *
 * This header is a clean-room, OpenCL-like convenience layer for tools that
 * want to describe queues, buffers, kernel dispatches, status records, and
 * metrics while driving the existing Ventus Verilator simulation API.
 *
 * It is intentionally non-conformant: it is not OpenCL, not a Vivante ABI, not
 * a proprietary command stream, not firmware, and not a compatibility claim.
 * All fields are proxy descriptors owned by the Ventus/Celviz simulator
 * integration boundary.
 */

#include <stdbool.h>
#include <stdint.h>

#ifndef CELVIZ_GPGPU_DLL_PUBLIC
#ifdef DLL_PUBLIC
#define CELVIZ_GPGPU_DLL_PUBLIC DLL_PUBLIC
#elif defined(__GNUC__) && __GNUC__ >= 4
#define CELVIZ_GPGPU_DLL_PUBLIC __attribute__((visibility("default")))
#else
#define CELVIZ_GPGPU_DLL_PUBLIC
#endif
#endif

#ifdef __cplusplus
extern "C" {
#endif

#ifndef VENTUS_RTLSIM_TYPES_DEFINED
typedef struct ventus_rtlsim_t ventus_rtlsim_t;
typedef struct ventus_kernel_metadata_t ventus_kernel_metadata_t;
#endif

#define CELVIZ_GPGPU_RUNTIME_PROXY_ABI_VERSION 1u
#define CELVIZ_GPGPU_RUNTIME_PROXY_MAGIC 0x31555643u /* "CVU1", little-endian */

typedef enum {
    CELVIZ_GPGPU_TIER_UNKNOWN = 0,
    CELVIZ_GPGPU_TIER_NANO = 1,
    CELVIZ_GPGPU_TIER_NANO_ULTRA = 2,
    CELVIZ_GPGPU_TIER_NANO_ULTRA31 = 3,
    CELVIZ_GPGPU_TIER_MICRO = 0x10,
    CELVIZ_GPGPU_TIER_SMALL = 0x11,
    CELVIZ_GPGPU_TIER_FULL = 0x12,
} celviz_gpgpu_tier_id_t;

typedef enum {
    CELVIZ_GPGPU_FP_MODE_DEFAULT = 0,
    CELVIZ_GPGPU_FP_MODE_FP32 = 1,
    CELVIZ_GPGPU_FP_MODE_FP16 = 2,
    CELVIZ_GPGPU_FP_MODE_MIXED = 3,
} celviz_gpgpu_fp_mode_t;

typedef enum {
    CELVIZ_GPGPU_SCHED_HINT_DEFAULT = 0,
    CELVIZ_GPGPU_SCHED_HINT_LATENCY = 1,
    CELVIZ_GPGPU_SCHED_HINT_THROUGHPUT = 2,
    CELVIZ_GPGPU_SCHED_HINT_FAIR_SHARE = 3,
} celviz_gpgpu_scheduler_hint_t;

typedef enum {
    CELVIZ_GPGPU_QUEUE_IN_ORDER = 1u << 0,
    CELVIZ_GPGPU_QUEUE_PROFILING = 1u << 1,
    CELVIZ_GPGPU_QUEUE_OUT_OF_ORDER = 1u << 2,
    CELVIZ_GPGPU_QUEUE_SOFTWARE_PROXY = 1u << 8,
} celviz_gpgpu_queue_flags_t;

typedef enum {
    CELVIZ_GPGPU_BUFFER_READ = 1u << 0,
    CELVIZ_GPGPU_BUFFER_WRITE = 1u << 1,
    CELVIZ_GPGPU_BUFFER_READ_WRITE = CELVIZ_GPGPU_BUFFER_READ | CELVIZ_GPGPU_BUFFER_WRITE,
    CELVIZ_GPGPU_BUFFER_HOST_VISIBLE = 1u << 8,
    CELVIZ_GPGPU_BUFFER_DEVICE_LOCAL = 1u << 9,
} celviz_gpgpu_buffer_flags_t;

typedef enum {
    CELVIZ_GPGPU_BINDING_GLOBAL = 0,
    CELVIZ_GPGPU_BINDING_ARGUMENT = 1,
    CELVIZ_GPGPU_BINDING_CONSTANT = 2,
    CELVIZ_GPGPU_BINDING_LOCAL = 3,
    CELVIZ_GPGPU_BINDING_PRIVATE = 4,
    CELVIZ_GPGPU_BINDING_CODE = 5,
    CELVIZ_GPGPU_BINDING_METADATA = 6,
} celviz_gpgpu_binding_kind_t;

typedef enum {
    CELVIZ_GPGPU_OPCODE_NOP = 0x0000,
    CELVIZ_GPGPU_OPCODE_KERNEL_DISPATCH = 0x0001,
    CELVIZ_GPGPU_OPCODE_DMA_COPY = 0x0002,
    CELVIZ_GPGPU_OPCODE_DMA_FILL = 0x0003,
    CELVIZ_GPGPU_OPCODE_BARRIER = 0x0004,
    CELVIZ_GPGPU_OPCODE_SET_SCHEDULER_CONFIG = 0x0005,
    CELVIZ_GPGPU_OPCODE_SET_SHADER_MODE = 0x0006,
    CELVIZ_GPGPU_OPCODE_COUNTER_SNAPSHOT = 0x0007,
    CELVIZ_GPGPU_OPCODE_FAULT = 0x0008,
} celviz_gpgpu_opcode_t;

typedef enum {
    CELVIZ_GPGPU_COMMAND_NEW = 0,
    CELVIZ_GPGPU_COMMAND_QUEUED = 1,
    CELVIZ_GPGPU_COMMAND_SUBMITTED = 2,
    CELVIZ_GPGPU_COMMAND_RUNNING = 3,
    CELVIZ_GPGPU_COMMAND_COMPLETE = 4,
    CELVIZ_GPGPU_COMMAND_ERROR = 5,
    CELVIZ_GPGPU_COMMAND_CANCELLED = 6,
    CELVIZ_GPGPU_COMMAND_TIMEOUT = 7,
} celviz_gpgpu_command_status_t;

typedef enum {
    CELVIZ_GPGPU_EVENT_NONE = 0,
    CELVIZ_GPGPU_EVENT_COMMAND_COMPLETE = 1u << 0,
    CELVIZ_GPGPU_EVENT_COMMAND_ERROR = 1u << 1,
    CELVIZ_GPGPU_EVENT_COUNTERS_CAPTURED = 1u << 2,
    CELVIZ_GPGPU_EVENT_MMU_FAULT = 1u << 3,
    CELVIZ_GPGPU_EVENT_WATCHDOG = 1u << 4,
} celviz_gpgpu_event_flags_t;

typedef enum {
    CELVIZ_GPGPU_ERROR_OK = 0x0000,
    CELVIZ_GPGPU_ERROR_UNSUPPORTED_OPCODE = 0x0005,
    CELVIZ_GPGPU_ERROR_BAD_QUEUE = 0x0006,
    CELVIZ_GPGPU_ERROR_BAD_DISPATCH = 0x0007,
    CELVIZ_GPGPU_ERROR_BAD_DMA = 0x0008,
    CELVIZ_GPGPU_ERROR_MMU_FAULT = 0x0009,
    CELVIZ_GPGPU_ERROR_FENCE_WAIT = 0x0100,
    CELVIZ_GPGPU_ERROR_INJECTED = 0x0101,
    CELVIZ_GPGPU_ERROR_RTLSIM_FATAL = 0x0200,
    CELVIZ_GPGPU_ERROR_RTLSIM_TIME_EXCEEDED = 0x0201,
} celviz_gpgpu_error_t;

typedef struct {
    uint32_t abi_version;
    celviz_gpgpu_tier_id_t tier_id;
    const char* tier_name;
    const char* public_reference_tier;
    uint32_t queue_count;
    uint32_t shader_unit_count;
    uint32_t warp_size;
    uint32_t max_workgroup_size;
    uint32_t address_bits;
    uint32_t fp32_ops_per_cycle;
    uint32_t fp16_ops_per_cycle;
    uint32_t flags;
} celviz_gpgpu_device_tier_t;

typedef struct {
    uint32_t queue_id;
    uint32_t context_id;
    uint32_t priority;
    uint32_t flags;
    uint64_t ring_base;
    uint64_t ring_size_bytes;
    uint64_t head;
    uint64_t tail;
    uint64_t doorbell;
    uint64_t submitted;
    uint64_t retired;
    uint64_t errors;
} celviz_gpgpu_queue_t;

typedef struct {
    const char* id;
    celviz_gpgpu_binding_kind_t binding;
    uint32_t index;
    uint32_t flags;
    uint64_t device_address;
    uint64_t size_bytes;
    uint64_t alloc_size_bytes;
    uint64_t offset_bytes;
    void* host_ptr;
} celviz_gpgpu_buffer_binding_t;

typedef struct {
    const char* name;
    uint64_t kernel_entry;
    uint64_t arg_buffer;
    uint32_t arg_size_bytes;
    uint32_t grid[3];
    uint32_t local[3];
    uint32_t warp_size;
    uint32_t warps_per_workgroup;
    uint32_t shared_bytes;
    uint32_t private_bytes_per_thread;
    uint16_t sgpr_count;
    uint16_t vgpr_count;
    celviz_gpgpu_fp_mode_t required_fp_mode;
    celviz_gpgpu_scheduler_hint_t scheduler_hint;
    const celviz_gpgpu_buffer_binding_t* bindings;
    uint32_t binding_count;

    /*
     * Optional bridge to the native Ventus metadata accepted by
     * ventus_rtlsim_add_kernel(). When set, runtime code should treat this as
     * the authoritative executable descriptor for RTL simulation.
     */
    const ventus_kernel_metadata_t* ventus_metadata;
} celviz_gpgpu_kernel_descriptor_t;

typedef struct {
    uint32_t abi_version;
    uint32_t queue_id;
    uint32_t context_id;
    uint32_t flags;
    uint64_t sequence;
    celviz_gpgpu_opcode_t opcode;
    celviz_gpgpu_command_status_t status;
    celviz_gpgpu_error_t error;
    uint64_t submit_tag;
    uint64_t submit_time;
    uint64_t start_time;
    uint64_t end_time;
} celviz_gpgpu_command_status_record_t;

typedef struct {
    uint32_t abi_version;
    uint32_t event_flags;
    celviz_gpgpu_command_status_record_t command;
    uint64_t fault_address;
    uint32_t fault_access;
    uint32_t shader_context;
} celviz_gpgpu_event_status_t;

typedef struct {
    uint64_t commands_submitted;
    uint64_t commands_completed;
    uint64_t commands_failed;
    uint64_t kernel_dispatches;
    uint64_t dma_copies;
    uint64_t dma_fills;
    uint64_t fence_waits;
    uint64_t fence_signals;
    uint64_t resets;
    uint64_t bytes_read;
    uint64_t bytes_written;
    uint64_t bytes_moved;
    uint64_t axi_read_beats;
    uint64_t axi_write_beats;
    uint64_t axi_read_transactions;
    uint64_t axi_write_transactions;
    uint64_t completion_interrupts;
    uint64_t error_interrupts;
    uint64_t mmu_faults;
    uint64_t queue_errors;
    uint64_t scheduler_faults;
    uint64_t rtlsim_time;
} celviz_gpgpu_runtime_metrics_t;

typedef struct {
    ventus_rtlsim_t* sim;
    celviz_gpgpu_device_tier_t device;
    celviz_gpgpu_queue_t* queues;
    uint32_t queue_count;
    void* user_data;
} celviz_gpgpu_runtime_proxy_t;

CELVIZ_GPGPU_DLL_PUBLIC void celviz_gpgpu_device_tier_get_default(celviz_gpgpu_device_tier_t* out_device);

CELVIZ_GPGPU_DLL_PUBLIC celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_attach(
    celviz_gpgpu_runtime_proxy_t* proxy, ventus_rtlsim_t* sim, const celviz_gpgpu_device_tier_t* device,
    celviz_gpgpu_queue_t* queues, uint32_t queue_count
);

CELVIZ_GPGPU_DLL_PUBLIC void celviz_gpgpu_runtime_proxy_detach(celviz_gpgpu_runtime_proxy_t* proxy);

CELVIZ_GPGPU_DLL_PUBLIC bool celviz_gpgpu_runtime_proxy_get_device(
    const celviz_gpgpu_runtime_proxy_t* proxy, celviz_gpgpu_device_tier_t* out_device
);

CELVIZ_GPGPU_DLL_PUBLIC uint32_t celviz_gpgpu_runtime_proxy_get_queue_count(
    const celviz_gpgpu_runtime_proxy_t* proxy
);

CELVIZ_GPGPU_DLL_PUBLIC bool celviz_gpgpu_runtime_proxy_get_queue_snapshot(
    const celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_index, celviz_gpgpu_queue_t* out_queue
);

CELVIZ_GPGPU_DLL_PUBLIC bool celviz_gpgpu_runtime_proxy_get_queue_by_id(
    const celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id, celviz_gpgpu_queue_t* out_queue
);

CELVIZ_GPGPU_DLL_PUBLIC uint64_t celviz_gpgpu_runtime_proxy_get_pending_count(
    const celviz_gpgpu_runtime_proxy_t* proxy
);

CELVIZ_GPGPU_DLL_PUBLIC bool celviz_gpgpu_runtime_proxy_get_queue_pending_count(
    const celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id, uint64_t* out_pending
);

CELVIZ_GPGPU_DLL_PUBLIC celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_reset_queue(
    celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id, bool cancel_pending,
    celviz_gpgpu_event_status_t* out_event
);

CELVIZ_GPGPU_DLL_PUBLIC celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_submit_kernel(
    celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id, const celviz_gpgpu_kernel_descriptor_t* kernel,
    void (*finish_callback)(const ventus_kernel_metadata_t*), celviz_gpgpu_command_status_record_t* out_status
);

CELVIZ_GPGPU_DLL_PUBLIC celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_submit_copy_h2d(
    celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id, uint64_t dst, const void* src, uint64_t size,
    celviz_gpgpu_command_status_record_t* out_status
);

CELVIZ_GPGPU_DLL_PUBLIC celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_submit_copy_d2h(
    celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id, void* dst, uint64_t src, uint64_t size,
    celviz_gpgpu_command_status_record_t* out_status
);

CELVIZ_GPGPU_DLL_PUBLIC celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_submit_fill(
    celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id, uint64_t dst, uint32_t pattern_u32, uint64_t size,
    celviz_gpgpu_command_status_record_t* out_status
);

CELVIZ_GPGPU_DLL_PUBLIC celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_inject_next_error(
    celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id, celviz_gpgpu_error_t error,
    uint64_t fault_address
);

CELVIZ_GPGPU_DLL_PUBLIC celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_submit_fault(
    celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id, celviz_gpgpu_error_t error,
    uint64_t fault_address, celviz_gpgpu_command_status_record_t* out_status
);

CELVIZ_GPGPU_DLL_PUBLIC celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_step(
    celviz_gpgpu_runtime_proxy_t* proxy, celviz_gpgpu_event_status_t* out_event
);

CELVIZ_GPGPU_DLL_PUBLIC bool celviz_gpgpu_runtime_proxy_get_command_status(
    const celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id, uint64_t sequence,
    celviz_gpgpu_command_status_record_t* out_status
);

CELVIZ_GPGPU_DLL_PUBLIC bool celviz_gpgpu_runtime_proxy_get_last_event(
    const celviz_gpgpu_runtime_proxy_t* proxy, celviz_gpgpu_event_status_t* out_event
);

CELVIZ_GPGPU_DLL_PUBLIC bool celviz_gpgpu_runtime_proxy_get_metrics(
    const celviz_gpgpu_runtime_proxy_t* proxy, celviz_gpgpu_runtime_metrics_t* out_metrics
);

CELVIZ_GPGPU_DLL_PUBLIC bool celviz_gpgpu_runtime_proxy_reset_metrics(celviz_gpgpu_runtime_proxy_t* proxy);

CELVIZ_GPGPU_DLL_PUBLIC uint64_t celviz_gpgpu_runtime_proxy_get_fence_value(
    const celviz_gpgpu_runtime_proxy_t* proxy
);

CELVIZ_GPGPU_DLL_PUBLIC bool celviz_gpgpu_runtime_proxy_get_named_fence_value(
    const celviz_gpgpu_runtime_proxy_t* proxy, const char* fence_name, uint64_t* out_fence_value
);

CELVIZ_GPGPU_DLL_PUBLIC celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_signal_fence(
    celviz_gpgpu_runtime_proxy_t* proxy, uint64_t fence_value, celviz_gpgpu_event_status_t* out_event
);

CELVIZ_GPGPU_DLL_PUBLIC celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_signal_named_fence(
    celviz_gpgpu_runtime_proxy_t* proxy, const char* fence_name, uint64_t fence_value,
    celviz_gpgpu_event_status_t* out_event
);

CELVIZ_GPGPU_DLL_PUBLIC celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_wait_fence(
    celviz_gpgpu_runtime_proxy_t* proxy, uint64_t fence_value, uint64_t max_steps,
    celviz_gpgpu_event_status_t* out_event
);

CELVIZ_GPGPU_DLL_PUBLIC celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_wait_named_fence(
    celviz_gpgpu_runtime_proxy_t* proxy, const char* fence_name, uint64_t fence_value, uint64_t max_steps,
    celviz_gpgpu_event_status_t* out_event
);

static inline bool celviz_gpgpu_command_status_is_terminal(celviz_gpgpu_command_status_t status) {
    return status == CELVIZ_GPGPU_COMMAND_COMPLETE || status == CELVIZ_GPGPU_COMMAND_ERROR ||
           status == CELVIZ_GPGPU_COMMAND_CANCELLED || status == CELVIZ_GPGPU_COMMAND_TIMEOUT;
}

static inline celviz_gpgpu_command_status_record_t celviz_gpgpu_command_status_make(
    uint32_t queue_id, uint64_t sequence, celviz_gpgpu_opcode_t opcode
) {
    celviz_gpgpu_command_status_record_t status = {
        CELVIZ_GPGPU_RUNTIME_PROXY_ABI_VERSION,
        queue_id,
        0,
        0,
        sequence,
        opcode,
        CELVIZ_GPGPU_COMMAND_NEW,
        CELVIZ_GPGPU_ERROR_OK,
        0,
        0,
        0,
        0,
    };
    return status;
}

static inline void celviz_gpgpu_runtime_metrics_accumulate(
    celviz_gpgpu_runtime_metrics_t* dst, const celviz_gpgpu_runtime_metrics_t* src
) {
    if (dst == 0 || src == 0) {
        return;
    }
    dst->commands_submitted += src->commands_submitted;
    dst->commands_completed += src->commands_completed;
    dst->commands_failed += src->commands_failed;
    dst->kernel_dispatches += src->kernel_dispatches;
    dst->dma_copies += src->dma_copies;
    dst->dma_fills += src->dma_fills;
    dst->fence_waits += src->fence_waits;
    dst->fence_signals += src->fence_signals;
    dst->resets += src->resets;
    dst->bytes_read += src->bytes_read;
    dst->bytes_written += src->bytes_written;
    dst->bytes_moved += src->bytes_moved;
    dst->axi_read_beats += src->axi_read_beats;
    dst->axi_write_beats += src->axi_write_beats;
    dst->axi_read_transactions += src->axi_read_transactions;
    dst->axi_write_transactions += src->axi_write_transactions;
    dst->completion_interrupts += src->completion_interrupts;
    dst->error_interrupts += src->error_interrupts;
    dst->mmu_faults += src->mmu_faults;
    dst->queue_errors += src->queue_errors;
    dst->scheduler_faults += src->scheduler_faults;
    dst->rtlsim_time += src->rtlsim_time;
}

#ifdef VENTUS_RTLSIM_API_INCLUDED
static inline bool celviz_gpgpu_proxy_is_idle(const celviz_gpgpu_runtime_proxy_t* proxy) {
    return proxy != 0 && proxy->sim != 0 && ventus_rtlsim_is_idle(proxy->sim);
}

static inline uint64_t celviz_gpgpu_proxy_get_time(const celviz_gpgpu_runtime_proxy_t* proxy) {
    return proxy != 0 && proxy->sim != 0 ? ventus_rtlsim_get_time(proxy->sim) : 0;
}

static inline bool celviz_gpgpu_proxy_copy_h2d(
    celviz_gpgpu_runtime_proxy_t* proxy, uint64_t dst, const void* src, uint64_t size
) {
    return proxy != 0 && proxy->sim != 0 && ventus_rtlsim_pmemcpy_h2d(proxy->sim, dst, src, size);
}

static inline bool celviz_gpgpu_proxy_copy_d2h(
    celviz_gpgpu_runtime_proxy_t* proxy, void* dst, uint64_t src, uint64_t size
) {
    return proxy != 0 && proxy->sim != 0 && ventus_rtlsim_pmemcpy_d2h(proxy->sim, dst, src, size);
}

static inline bool celviz_gpgpu_proxy_enqueue_kernel(
    celviz_gpgpu_runtime_proxy_t* proxy, const celviz_gpgpu_kernel_descriptor_t* kernel,
    void (*finish_callback)(const ventus_kernel_metadata_t*)
) {
    if (proxy == 0 || proxy->sim == 0 || kernel == 0 || kernel->ventus_metadata == 0) {
        return false;
    }
    ventus_rtlsim_add_kernel(proxy->sim, kernel->ventus_metadata, finish_callback);
    return true;
}

static inline void celviz_gpgpu_command_status_update_from_rtlsim_step(
    celviz_gpgpu_command_status_record_t* status, const ventus_rtlsim_step_result_t* step, uint64_t rtlsim_time
) {
    if (status == 0 || step == 0) {
        return;
    }
    if (step->error) {
        status->status = CELVIZ_GPGPU_COMMAND_ERROR;
        status->error = CELVIZ_GPGPU_ERROR_RTLSIM_FATAL;
        status->end_time = rtlsim_time;
    } else if (step->time_exceed) {
        status->status = CELVIZ_GPGPU_COMMAND_TIMEOUT;
        status->error = CELVIZ_GPGPU_ERROR_RTLSIM_TIME_EXCEEDED;
        status->end_time = rtlsim_time;
    } else if (step->idle) {
        status->status = CELVIZ_GPGPU_COMMAND_COMPLETE;
        status->error = CELVIZ_GPGPU_ERROR_OK;
        status->end_time = rtlsim_time;
    }
}
#endif

#ifdef __cplusplus
} // extern "C"
#endif
