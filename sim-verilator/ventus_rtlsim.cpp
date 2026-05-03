#include "ventus_rtlsim_impl.hpp"
#include "gvmref_interface.h" // apis from spike repo
#include <algorithm>
#include <cstring>
#include <ctime>
#include <list>
#include <string>
#include <unordered_map>
#include <vector>

struct celviz_gpgpu_runtime_command_t {
    ventus_rtlsim_t* sim = nullptr;
    celviz_gpgpu_command_status_record_t status{};
    ventus_kernel_metadata_t metadata{};
    std::vector<uint64_t> buffer_base;
    std::vector<uint64_t> buffer_size;
    std::vector<uint64_t> buffer_allocsize;
    std::vector<celviz_gpgpu_buffer_binding_t> bindings;
    void* metadata_user_data = nullptr;
    void (*finish_callback)(const ventus_kernel_metadata_t*) = nullptr;
};

struct celviz_gpgpu_runtime_state_t {
    celviz_gpgpu_runtime_proxy_t* proxy = nullptr;
    std::vector<celviz_gpgpu_queue_t> owned_queues;
    std::list<celviz_gpgpu_runtime_command_t> commands;
    celviz_gpgpu_runtime_metrics_t metrics{};
    celviz_gpgpu_event_status_t last_event{};
    std::unordered_map<std::string, uint64_t> named_fences;
    uint64_t next_sequence = 1;
    uint64_t fence_value = 0;
    bool inject_next_error = false;
    uint32_t inject_queue_id = 0;
    celviz_gpgpu_error_t inject_error = CELVIZ_GPGPU_ERROR_INJECTED;
    uint64_t inject_fault_address = 0;
};

ventus_rtlsim_t::~ventus_rtlsim_t() = default;

static celviz_gpgpu_command_status_record_t celviz_make_status(
    uint32_t queue_id, uint64_t sequence, celviz_gpgpu_opcode_t opcode, uint64_t time
) {
    celviz_gpgpu_command_status_record_t status
        = celviz_gpgpu_command_status_make(queue_id, sequence, opcode);
    status.status = CELVIZ_GPGPU_COMMAND_SUBMITTED;
    status.submit_tag = sequence;
    status.submit_time = time;
    return status;
}

static void celviz_reset_event(celviz_gpgpu_event_status_t* event) {
    if (event == nullptr) {
        return;
    }
    std::memset(event, 0, sizeof(*event));
    event->abi_version = CELVIZ_GPGPU_RUNTIME_PROXY_ABI_VERSION;
    event->command = celviz_gpgpu_command_status_make(0, 0, CELVIZ_GPGPU_OPCODE_NOP);
}

static celviz_gpgpu_runtime_state_t* celviz_get_state(celviz_gpgpu_runtime_proxy_t* proxy) {
    if (proxy == nullptr || proxy->sim == nullptr || proxy->sim->celviz_gpgpu_runtime == nullptr) {
        return nullptr;
    }
    return proxy->sim->celviz_gpgpu_runtime.get();
}

static const celviz_gpgpu_runtime_state_t* celviz_get_state_const(const celviz_gpgpu_runtime_proxy_t* proxy) {
    if (proxy == nullptr || proxy->sim == nullptr || proxy->sim->celviz_gpgpu_runtime == nullptr) {
        return nullptr;
    }
    return proxy->sim->celviz_gpgpu_runtime.get();
}

static celviz_gpgpu_queue_t* celviz_find_queue(celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id) {
    if (proxy == nullptr || proxy->queues == nullptr) {
        return nullptr;
    }
    for (uint32_t i = 0; i < proxy->queue_count; ++i) {
        if (proxy->queues[i].queue_id == queue_id) {
            return &proxy->queues[i];
        }
    }
    return nullptr;
}

static const celviz_gpgpu_queue_t* celviz_find_queue_const(
    const celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id
) {
    if (proxy == nullptr || proxy->queues == nullptr) {
        return nullptr;
    }
    for (uint32_t i = 0; i < proxy->queue_count; ++i) {
        if (proxy->queues[i].queue_id == queue_id) {
            return &proxy->queues[i];
        }
    }
    return nullptr;
}

static void celviz_record_event(
    celviz_gpgpu_runtime_state_t* state, uint32_t event_flags,
    const celviz_gpgpu_command_status_record_t* command, uint64_t fault_address = 0,
    uint32_t fault_access = 0, uint32_t shader_context = 0
) {
    if (state == nullptr) {
        return;
    }
    celviz_reset_event(&state->last_event);
    state->last_event.event_flags = event_flags;
    if (command != nullptr) {
        state->last_event.command = *command;
    }
    state->last_event.fault_address = fault_address;
    state->last_event.fault_access = fault_access;
    state->last_event.shader_context = shader_context;
}

static uint32_t celviz_error_event_flags(celviz_gpgpu_error_t error) {
    uint32_t flags = CELVIZ_GPGPU_EVENT_COMMAND_ERROR;
    if (error == CELVIZ_GPGPU_ERROR_MMU_FAULT) {
        flags |= CELVIZ_GPGPU_EVENT_MMU_FAULT;
    }
    if (error == CELVIZ_GPGPU_ERROR_RTLSIM_TIME_EXCEEDED || error == CELVIZ_GPGPU_ERROR_FENCE_WAIT) {
        flags |= CELVIZ_GPGPU_EVENT_WATCHDOG;
    }
    return flags;
}

static void celviz_submit_to_queue(celviz_gpgpu_queue_t* queue) {
    if (queue == nullptr) {
        return;
    }
    queue->tail++;
    queue->doorbell++;
    queue->submitted++;
}

static void celviz_finish_command(
    celviz_gpgpu_runtime_state_t* state, celviz_gpgpu_runtime_proxy_t* proxy,
    celviz_gpgpu_runtime_command_t* command, celviz_gpgpu_command_status_t terminal_status,
    celviz_gpgpu_error_t error, uint64_t time, uint64_t fault_address = 0
) {
    if (state == nullptr || command == nullptr || celviz_gpgpu_command_status_is_terminal(command->status.status)) {
        return;
    }

    command->status.status = terminal_status;
    command->status.error = error;
    command->status.end_time = time;
    state->fence_value = std::max(state->fence_value, command->status.sequence);
    const bool counts_as_error =
        terminal_status == CELVIZ_GPGPU_COMMAND_ERROR || terminal_status == CELVIZ_GPGPU_COMMAND_TIMEOUT ||
        error != CELVIZ_GPGPU_ERROR_OK;

    celviz_gpgpu_queue_t* queue = celviz_find_queue(proxy, command->status.queue_id);
    if (queue != nullptr) {
        queue->head++;
        queue->retired++;
        if (counts_as_error) {
            queue->errors++;
            state->metrics.queue_errors++;
        }
    }

    if (terminal_status == CELVIZ_GPGPU_COMMAND_COMPLETE) {
        state->metrics.commands_completed++;
        state->metrics.completion_interrupts++;
        celviz_record_event(state, CELVIZ_GPGPU_EVENT_COMMAND_COMPLETE, &command->status);
    } else {
        state->metrics.commands_failed++;
        if (counts_as_error) {
            state->metrics.error_interrupts++;
        }
        if (error == CELVIZ_GPGPU_ERROR_MMU_FAULT) {
            state->metrics.mmu_faults++;
        }
        celviz_record_event(state, celviz_error_event_flags(error), &command->status, fault_address);
    }
}

static void celviz_mark_submitted_commands_running(celviz_gpgpu_runtime_state_t* state, uint64_t time) {
    if (state == nullptr) {
        return;
    }
    for (auto& command : state->commands) {
        if (command.status.status == CELVIZ_GPGPU_COMMAND_SUBMITTED ||
            command.status.status == CELVIZ_GPGPU_COMMAND_QUEUED) {
            command.status.status = CELVIZ_GPGPU_COMMAND_RUNNING;
            if (command.status.start_time == 0) {
                command.status.start_time = time;
            }
        }
    }
}

static void celviz_fail_nonterminal_commands(
    celviz_gpgpu_runtime_state_t* state, celviz_gpgpu_runtime_proxy_t* proxy,
    celviz_gpgpu_command_status_t terminal_status, celviz_gpgpu_error_t error, uint64_t time
) {
    if (state == nullptr) {
        return;
    }
    for (auto& command : state->commands) {
        celviz_finish_command(state, proxy, &command, terminal_status, error, time);
    }
}

static uint64_t celviz_binding_device_address(const celviz_gpgpu_buffer_binding_t& binding) {
    return binding.device_address + binding.offset_bytes;
}

static bool celviz_sync_kernel_inputs(celviz_gpgpu_runtime_command_t* command) {
    if (command == nullptr || command->sim == nullptr) {
        return false;
    }
    celviz_gpgpu_runtime_state_t* state = command->sim->celviz_gpgpu_runtime.get();
    for (const auto& binding : command->bindings) {
        if (binding.host_ptr == nullptr || binding.size_bytes == 0 ||
            (binding.flags & CELVIZ_GPGPU_BUFFER_READ) == 0) {
            continue;
        }
        if (!ventus_rtlsim_pmemcpy_h2d(
                command->sim, celviz_binding_device_address(binding), binding.host_ptr, binding.size_bytes
            )) {
            return false;
        }
        if (state != nullptr) {
            state->metrics.bytes_written += binding.size_bytes;
            state->metrics.bytes_moved += binding.size_bytes;
        }
    }
    return true;
}

static bool celviz_sync_kernel_outputs(celviz_gpgpu_runtime_command_t* command) {
    if (command == nullptr || command->sim == nullptr) {
        return false;
    }
    celviz_gpgpu_runtime_state_t* state = command->sim->celviz_gpgpu_runtime.get();
    for (const auto& binding : command->bindings) {
        if (binding.host_ptr == nullptr || binding.size_bytes == 0 ||
            (binding.flags & CELVIZ_GPGPU_BUFFER_WRITE) == 0) {
            continue;
        }
        if (!ventus_rtlsim_pmemcpy_d2h(
                command->sim, binding.host_ptr, celviz_binding_device_address(binding), binding.size_bytes
            )) {
            return false;
        }
        if (state != nullptr) {
            state->metrics.bytes_read += binding.size_bytes;
            state->metrics.bytes_moved += binding.size_bytes;
        }
    }
    return true;
}

static void celviz_runtime_kernel_finished(const ventus_kernel_metadata_t* metadata) {
    if (metadata == nullptr || metadata->data == nullptr) {
        return;
    }
    auto* command = static_cast<celviz_gpgpu_runtime_command_t*>(metadata->data);
    if (command->sim == nullptr || command->sim->celviz_gpgpu_runtime == nullptr) {
        return;
    }

    celviz_gpgpu_runtime_state_t* state = command->sim->celviz_gpgpu_runtime.get();
    if (celviz_gpgpu_command_status_is_terminal(command->status.status)) {
        return;
    }
    celviz_gpgpu_error_t error = CELVIZ_GPGPU_ERROR_OK;
    if (!celviz_sync_kernel_outputs(command)) {
        error = CELVIZ_GPGPU_ERROR_MMU_FAULT;
    }

    if (command->finish_callback != nullptr) {
        ventus_kernel_metadata_t callback_metadata = *metadata;
        callback_metadata.data = command->metadata_user_data;
        command->finish_callback(&callback_metadata);
    }

    celviz_finish_command(
        state, state->proxy, command,
        error == CELVIZ_GPGPU_ERROR_OK ? CELVIZ_GPGPU_COMMAND_COMPLETE : CELVIZ_GPGPU_COMMAND_ERROR, error,
        ventus_rtlsim_get_time(command->sim)
    );
}

static void celviz_fill_default_queue(celviz_gpgpu_queue_t* queue) {
    if (queue == nullptr) {
        return;
    }
    std::memset(queue, 0, sizeof(*queue));
    queue->queue_id = 0;
    queue->flags = CELVIZ_GPGPU_QUEUE_IN_ORDER | CELVIZ_GPGPU_QUEUE_PROFILING |
                   CELVIZ_GPGPU_QUEUE_SOFTWARE_PROXY;
}

static uint64_t celviz_pending_command_count(const celviz_gpgpu_runtime_state_t* state) {
    if (state == nullptr) {
        return 0;
    }
    uint64_t pending = 0;
    for (const auto& command : state->commands) {
        if (!celviz_gpgpu_command_status_is_terminal(command.status.status)) {
            pending++;
        }
    }
    return pending;
}

static bool celviz_has_nonterminal_commands(const celviz_gpgpu_runtime_state_t* state) {
    return celviz_pending_command_count(state) != 0;
}

static uint64_t celviz_pending_command_count_for_queue(
    const celviz_gpgpu_runtime_state_t* state, uint32_t queue_id
) {
    if (state == nullptr) {
        return 0;
    }
    uint64_t pending = 0;
    for (const auto& command : state->commands) {
        if (command.status.queue_id == queue_id &&
            !celviz_gpgpu_command_status_is_terminal(command.status.status)) {
            pending++;
        }
    }
    return pending;
}

static bool celviz_take_injected_error(
    celviz_gpgpu_runtime_state_t* state, uint32_t queue_id, celviz_gpgpu_error_t* out_error,
    uint64_t* out_fault_address
) {
    if (state == nullptr || !state->inject_next_error || state->inject_queue_id != queue_id) {
        return false;
    }
    if (out_error != nullptr) {
        *out_error = state->inject_error;
    }
    if (out_fault_address != nullptr) {
        *out_fault_address = state->inject_fault_address;
    }
    state->inject_next_error = false;
    state->inject_error = CELVIZ_GPGPU_ERROR_INJECTED;
    state->inject_fault_address = 0;
    return true;
}

static void celviz_prepare_command_metadata(
    celviz_gpgpu_runtime_command_t* command, const celviz_gpgpu_kernel_descriptor_t* kernel
) {
    if (command == nullptr || kernel == nullptr) {
        return;
    }

    if (kernel->binding_count != 0 && kernel->bindings != nullptr) {
        command->bindings.assign(kernel->bindings, kernel->bindings + kernel->binding_count);
    }

    if (kernel->ventus_metadata != nullptr) {
        command->metadata = *kernel->ventus_metadata;
    } else {
        std::memset(&command->metadata, 0, sizeof(command->metadata));
        command->metadata.name = kernel->name != nullptr ? kernel->name : "celviz_kernel";
        command->metadata.startaddr = kernel->kernel_entry;
        command->metadata.kernel_id = 0;
        command->metadata.kernel_size[0] = kernel->grid[0] == 0 ? 1 : kernel->grid[0];
        command->metadata.kernel_size[1] = kernel->grid[1] == 0 ? 1 : kernel->grid[1];
        command->metadata.kernel_size[2] = kernel->grid[2] == 0 ? 1 : kernel->grid[2];
        command->metadata.wf_size = kernel->warp_size == 0 ? 32 : kernel->warp_size;
        command->metadata.wg_size = kernel->warps_per_workgroup == 0 ? 1 : kernel->warps_per_workgroup;
        command->metadata.metaDataBaseAddr = kernel->arg_buffer;
        command->metadata.ldsSize = kernel->shared_bytes;
        command->metadata.pdsSize = kernel->private_bytes_per_thread;
        command->metadata.sgprUsage = kernel->sgpr_count;
        command->metadata.vgprUsage = kernel->vgpr_count;

        for (const auto& binding : command->bindings) {
            if (binding.binding == CELVIZ_GPGPU_BINDING_PRIVATE) {
                command->metadata.pdsBaseAddr = celviz_binding_device_address(binding);
                break;
            }
        }

        command->metadata.num_buffer = command->bindings.size();
        command->buffer_base.reserve(command->bindings.size());
        command->buffer_size.reserve(command->bindings.size());
        command->buffer_allocsize.reserve(command->bindings.size());
        for (const auto& binding : command->bindings) {
            command->buffer_base.push_back(celviz_binding_device_address(binding));
            command->buffer_size.push_back(binding.size_bytes);
            command->buffer_allocsize.push_back(
                binding.alloc_size_bytes == 0 ? binding.size_bytes : binding.alloc_size_bytes
            );
        }
        command->metadata.buffer_base = command->buffer_base.empty() ? nullptr : command->buffer_base.data();
        command->metadata.buffer_size = command->buffer_size.empty() ? nullptr : command->buffer_size.data();
        command->metadata.buffer_allocsize
            = command->buffer_allocsize.empty() ? nullptr : command->buffer_allocsize.data();
    }

    command->metadata_user_data = command->metadata.data;
    command->metadata.data = command;
}

static char verilator_rand_seed_setting[128] = "+verilator+seed+10086";
static char* verilator_runtime_args_default[] = { verilator_rand_seed_setting };
extern "C" void ventus_rtlsim_get_default_config(ventus_rtlsim_config_t* config) {
    if (config == nullptr)
        return;

    config->sim_time_max = 1000000;
    config->log.console.enable = true;
    config->log.console.level = "info";
    config->log.file.enable = true;
    config->log.file.level = "trace";
    config->log.file.filename = "logs/ventus_rtlsim.log";
    config->log.level = "trace";
    config->pmem.pagesize = 4096;
    config->pmem.auto_alloc = 0;
    config->waveform.enable = true;
    config->waveform.time_begin = 0;
    config->waveform.time_end = -1;
    config->waveform.levels = 99;
    config->waveform.filename = "logs/ventus_rtlsim.fst";
    config->snapshot.enable = true;
    config->snapshot.time_interval = 100000;
    config->snapshot.num_max = 2;
    config->snapshot.filename = "logs/ventus_rtlsim.snapshot.fst";
    config->verilator.argc = 0;
    config->verilator.argv = nullptr;

    timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    snprintf(verilator_rand_seed_setting, sizeof(verilator_rand_seed_setting), "+verilator+seed+%ld", ts.tv_nsec);
    config->verilator.argc = sizeof(verilator_runtime_args_default) / sizeof(verilator_runtime_args_default[0]);
    config->verilator.argv = (const char**)(verilator_runtime_args_default);
}

extern "C" ventus_rtlsim_t* ventus_rtlsim_init(const ventus_rtlsim_config_t* config) {
    ventus_rtlsim_t* sim = new ventus_rtlsim_t();
    sim->constructor(config);
    return sim;
}
extern "C" void ventus_rtlsim_finish(ventus_rtlsim_t* sim, bool snapshot_rollback_forcing) {
    sim->destructor(snapshot_rollback_forcing);
    delete sim;
}
extern "C" const ventus_rtlsim_step_result_t* ventus_rtlsim_step(ventus_rtlsim_t* sim) { return sim->step(); }
extern "C" void ventus_rtlsim_icache_invalidate(ventus_rtlsim_t* sim) { sim->need_icache_invalidate = true; }
extern "C" uint64_t ventus_rtlsim_get_time(const ventus_rtlsim_t* sim) { return sim->contextp->time(); }
extern "C" bool ventus_rtlsim_is_idle(const ventus_rtlsim_t* sim) { return sim->cta->is_idle(); }

extern "C" void ventus_rtlsim_add_kernel__delay_data_loading(
    ventus_rtlsim_t* sim, const ventus_kernel_metadata_t* metadata,
    void (*load_data_callback)(const ventus_kernel_metadata_t*),
    void (*finish_callback)(const ventus_kernel_metadata_t*)
) {
    std::shared_ptr<Kernel> kernel
        = std::make_shared<Kernel>(metadata, load_data_callback, finish_callback, sim->logger);
    sim->cta->kernel_add(kernel);
}
extern "C" void ventus_rtlsim_add_kernel(
    ventus_rtlsim_t* sim, const ventus_kernel_metadata_t* metadata,
    void (*finish_callback)(const ventus_kernel_metadata_t*)
) {
    ventus_rtlsim_add_kernel__delay_data_loading(sim, metadata, nullptr, finish_callback);
}

extern "C" bool ventus_rtlsim_pmem_page_alloc(ventus_rtlsim_t* sim, paddr_t base) {
    return sim->pmem->page_alloc(base);
}
extern "C" bool ventus_rtlsim_pmem_page_free(ventus_rtlsim_t* sim, paddr_t base) { return sim->pmem->page_free(base); }
extern "C" bool ventus_rtlsim_pmemcpy_h2d(ventus_rtlsim_t* sim, paddr_t dst, const void* src, uint64_t size) {
    return sim->pmem->write(dst, src, size);
}
extern "C" bool ventus_rtlsim_pmemcpy_d2h(ventus_rtlsim_t* sim, void* dst, paddr_t src, uint64_t size) {
    return sim->pmem->read(src, dst, size);
}

extern "C" int ventus_rtlsim_get_parameter(const char* name, uint32_t* out_value) {
    if (name == nullptr || out_value == nullptr)
        return -1;
    auto it = rtl_parameters.find(name);
    if (it == rtl_parameters.end())
        return -2;
    *out_value = it->second;
    return 0;
}

extern "C" void celviz_gpgpu_device_tier_get_default(celviz_gpgpu_device_tier_t* out_device) {
    if (out_device == nullptr) {
        return;
    }
    std::memset(out_device, 0, sizeof(*out_device));
    out_device->abi_version = CELVIZ_GPGPU_RUNTIME_PROXY_ABI_VERSION;
    out_device->tier_id = CELVIZ_GPGPU_TIER_SMALL;
    out_device->tier_name = "Ventus RTL simulation proxy";
    out_device->public_reference_tier = "clean-room Celviz GPGPU proxy";
    out_device->queue_count = 1;
    out_device->shader_unit_count = 1;
    out_device->warp_size = 32;
    out_device->max_workgroup_size = 1024;
    out_device->address_bits = 64;
    out_device->fp32_ops_per_cycle = 1;
}

extern "C" celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_attach(
    celviz_gpgpu_runtime_proxy_t* proxy, ventus_rtlsim_t* sim, const celviz_gpgpu_device_tier_t* device,
    celviz_gpgpu_queue_t* queues, uint32_t queue_count
) {
    if (proxy == nullptr || sim == nullptr) {
        return CELVIZ_GPGPU_ERROR_BAD_QUEUE;
    }

    if (sim->celviz_gpgpu_runtime == nullptr) {
        sim->celviz_gpgpu_runtime = std::make_unique<celviz_gpgpu_runtime_state_t>();
    }
    celviz_gpgpu_runtime_state_t* state = sim->celviz_gpgpu_runtime.get();
    if (celviz_has_nonterminal_commands(state)) {
        return CELVIZ_GPGPU_ERROR_BAD_QUEUE;
    }
    state->proxy = proxy;
    state->commands.clear();
    state->metrics = {};
    state->named_fences.clear();
    state->next_sequence = 1;
    state->fence_value = 0;
    state->inject_next_error = false;
    state->inject_queue_id = 0;
    state->inject_error = CELVIZ_GPGPU_ERROR_INJECTED;
    state->inject_fault_address = 0;
    celviz_reset_event(&state->last_event);

    std::memset(proxy, 0, sizeof(*proxy));
    proxy->sim = sim;
    if (device != nullptr) {
        proxy->device = *device;
    } else {
        celviz_gpgpu_device_tier_get_default(&proxy->device);
    }

    if (queues != nullptr && queue_count != 0) {
        proxy->queues = queues;
        proxy->queue_count = queue_count;
    } else {
        state->owned_queues.resize(1);
        celviz_fill_default_queue(&state->owned_queues[0]);
        proxy->queues = state->owned_queues.data();
        proxy->queue_count = state->owned_queues.size();
    }

    if (proxy->device.queue_count == 0) {
        proxy->device.queue_count = proxy->queue_count;
    }
    return CELVIZ_GPGPU_ERROR_OK;
}

extern "C" void celviz_gpgpu_runtime_proxy_detach(celviz_gpgpu_runtime_proxy_t* proxy) {
    if (proxy == nullptr) {
        return;
    }
    celviz_gpgpu_runtime_state_t* state = celviz_get_state(proxy);
    if (state != nullptr && state->proxy == proxy) {
        state->proxy = nullptr;
    }
    proxy->sim = nullptr;
    proxy->queues = nullptr;
    proxy->queue_count = 0;
}

extern "C" bool celviz_gpgpu_runtime_proxy_get_device(
    const celviz_gpgpu_runtime_proxy_t* proxy, celviz_gpgpu_device_tier_t* out_device
) {
    if (proxy == nullptr || out_device == nullptr) {
        return false;
    }
    *out_device = proxy->device;
    return true;
}

extern "C" uint32_t celviz_gpgpu_runtime_proxy_get_queue_count(const celviz_gpgpu_runtime_proxy_t* proxy) {
    return proxy == nullptr ? 0 : proxy->queue_count;
}

extern "C" bool celviz_gpgpu_runtime_proxy_get_queue_snapshot(
    const celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_index, celviz_gpgpu_queue_t* out_queue
) {
    if (proxy == nullptr || out_queue == nullptr || proxy->queues == nullptr || queue_index >= proxy->queue_count) {
        return false;
    }
    *out_queue = proxy->queues[queue_index];
    return true;
}

extern "C" bool celviz_gpgpu_runtime_proxy_get_queue_by_id(
    const celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id, celviz_gpgpu_queue_t* out_queue
) {
    const celviz_gpgpu_queue_t* queue = celviz_find_queue_const(proxy, queue_id);
    if (queue == nullptr || out_queue == nullptr) {
        return false;
    }
    *out_queue = *queue;
    return true;
}

extern "C" uint64_t celviz_gpgpu_runtime_proxy_get_pending_count(const celviz_gpgpu_runtime_proxy_t* proxy) {
    return celviz_pending_command_count(celviz_get_state_const(proxy));
}

extern "C" bool celviz_gpgpu_runtime_proxy_get_queue_pending_count(
    const celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id, uint64_t* out_pending
) {
    const celviz_gpgpu_runtime_state_t* state = celviz_get_state_const(proxy);
    if (state == nullptr || out_pending == nullptr || celviz_find_queue_const(proxy, queue_id) == nullptr) {
        return false;
    }
    *out_pending = celviz_pending_command_count_for_queue(state, queue_id);
    return true;
}

extern "C" celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_reset_queue(
    celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id, bool cancel_pending,
    celviz_gpgpu_event_status_t* out_event
) {
    celviz_gpgpu_runtime_state_t* state = celviz_get_state(proxy);
    celviz_gpgpu_queue_t* queue = celviz_find_queue(proxy, queue_id);
    if (state == nullptr || queue == nullptr) {
        return CELVIZ_GPGPU_ERROR_BAD_QUEUE;
    }

    if (celviz_pending_command_count_for_queue(state, queue_id) != 0 && !cancel_pending) {
        return CELVIZ_GPGPU_ERROR_BAD_QUEUE;
    }

    if (cancel_pending) {
        uint64_t time = ventus_rtlsim_get_time(proxy->sim);
        for (auto& command : state->commands) {
            if (command.status.queue_id == queue_id &&
                !celviz_gpgpu_command_status_is_terminal(command.status.status)) {
                celviz_finish_command(
                    state, proxy, &command, CELVIZ_GPGPU_COMMAND_CANCELLED, CELVIZ_GPGPU_ERROR_OK, time
                );
            }
        }
    }

    queue->head = 0;
    queue->tail = 0;
    queue->doorbell = 0;
    queue->submitted = 0;
    queue->retired = 0;
    queue->errors = 0;
    state->metrics.resets++;
    if (state->inject_next_error && state->inject_queue_id == queue_id) {
        state->inject_next_error = false;
        state->inject_error = CELVIZ_GPGPU_ERROR_INJECTED;
        state->inject_fault_address = 0;
    }

    celviz_reset_event(&state->last_event);
    state->last_event.event_flags = CELVIZ_GPGPU_EVENT_COMMAND_COMPLETE;
    state->last_event.command = celviz_make_status(
        queue_id, state->next_sequence - 1, CELVIZ_GPGPU_OPCODE_NOP, ventus_rtlsim_get_time(proxy->sim)
    );
    state->last_event.command.status = CELVIZ_GPGPU_COMMAND_COMPLETE;
    state->last_event.command.end_time = state->last_event.command.submit_time;
    if (out_event != nullptr) {
        *out_event = state->last_event;
    }
    return CELVIZ_GPGPU_ERROR_OK;
}

extern "C" celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_submit_kernel(
    celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id, const celviz_gpgpu_kernel_descriptor_t* kernel,
    void (*finish_callback)(const ventus_kernel_metadata_t*), celviz_gpgpu_command_status_record_t* out_status
) {
    celviz_gpgpu_runtime_state_t* state = celviz_get_state(proxy);
    celviz_gpgpu_queue_t* queue = celviz_find_queue(proxy, queue_id);
    if (state == nullptr || queue == nullptr) {
        return CELVIZ_GPGPU_ERROR_BAD_QUEUE;
    }
    if (kernel == nullptr) {
        return CELVIZ_GPGPU_ERROR_BAD_DISPATCH;
    }

    state->commands.emplace_back();
    auto& command = state->commands.back();
    command.sim = proxy->sim;
    command.finish_callback = finish_callback;
    command.status = celviz_make_status(
        queue_id, state->next_sequence++, CELVIZ_GPGPU_OPCODE_KERNEL_DISPATCH, ventus_rtlsim_get_time(proxy->sim)
    );
    celviz_prepare_command_metadata(&command, kernel);

    celviz_submit_to_queue(queue);
    state->metrics.commands_submitted++;
    state->metrics.kernel_dispatches++;

    celviz_gpgpu_error_t injected_error = CELVIZ_GPGPU_ERROR_OK;
    uint64_t injected_fault_address = 0;
    if (celviz_take_injected_error(state, queue_id, &injected_error, &injected_fault_address)) {
        command.status.start_time = command.status.submit_time;
        celviz_finish_command(
            state, proxy, &command, CELVIZ_GPGPU_COMMAND_ERROR, injected_error,
            ventus_rtlsim_get_time(proxy->sim), injected_fault_address
        );
        if (out_status != nullptr) {
            *out_status = command.status;
        }
        return injected_error;
    }

    if (!celviz_sync_kernel_inputs(&command)) {
        celviz_finish_command(
            state, proxy, &command, CELVIZ_GPGPU_COMMAND_ERROR, CELVIZ_GPGPU_ERROR_MMU_FAULT,
            ventus_rtlsim_get_time(proxy->sim)
        );
        if (out_status != nullptr) {
            *out_status = command.status;
        }
        return CELVIZ_GPGPU_ERROR_MMU_FAULT;
    }

    ventus_rtlsim_add_kernel(proxy->sim, &command.metadata, celviz_runtime_kernel_finished);
    if (out_status != nullptr) {
        *out_status = command.status;
    }
    return CELVIZ_GPGPU_ERROR_OK;
}

extern "C" celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_submit_copy_h2d(
    celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id, uint64_t dst, const void* src, uint64_t size,
    celviz_gpgpu_command_status_record_t* out_status
) {
    celviz_gpgpu_runtime_state_t* state = celviz_get_state(proxy);
    celviz_gpgpu_queue_t* queue = celviz_find_queue(proxy, queue_id);
    if (state == nullptr || queue == nullptr) {
        return CELVIZ_GPGPU_ERROR_BAD_QUEUE;
    }
    if (src == nullptr && size != 0) {
        return CELVIZ_GPGPU_ERROR_BAD_DMA;
    }

    state->commands.emplace_back();
    auto& command = state->commands.back();
    command.sim = proxy->sim;
    command.status = celviz_make_status(
        queue_id, state->next_sequence++, CELVIZ_GPGPU_OPCODE_DMA_COPY, ventus_rtlsim_get_time(proxy->sim)
    );
    command.status.start_time = command.status.submit_time;

    celviz_submit_to_queue(queue);
    state->metrics.commands_submitted++;
    state->metrics.dma_copies++;

    celviz_gpgpu_error_t injected_error = CELVIZ_GPGPU_ERROR_OK;
    uint64_t injected_fault_address = 0;
    if (celviz_take_injected_error(state, queue_id, &injected_error, &injected_fault_address)) {
        celviz_finish_command(
            state, proxy, &command, CELVIZ_GPGPU_COMMAND_ERROR, injected_error,
            ventus_rtlsim_get_time(proxy->sim), injected_fault_address
        );
        if (out_status != nullptr) {
            *out_status = command.status;
        }
        return injected_error;
    }

    bool ok = ventus_rtlsim_pmemcpy_h2d(proxy->sim, dst, src, size);
    if (ok) {
        state->metrics.bytes_written += size;
        state->metrics.bytes_moved += size;
    }
    celviz_finish_command(
        state, proxy, &command, ok ? CELVIZ_GPGPU_COMMAND_COMPLETE : CELVIZ_GPGPU_COMMAND_ERROR,
        ok ? CELVIZ_GPGPU_ERROR_OK : CELVIZ_GPGPU_ERROR_MMU_FAULT, ventus_rtlsim_get_time(proxy->sim)
    );
    if (out_status != nullptr) {
        *out_status = command.status;
    }
    return ok ? CELVIZ_GPGPU_ERROR_OK : CELVIZ_GPGPU_ERROR_MMU_FAULT;
}

extern "C" celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_submit_copy_d2h(
    celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id, void* dst, uint64_t src, uint64_t size,
    celviz_gpgpu_command_status_record_t* out_status
) {
    celviz_gpgpu_runtime_state_t* state = celviz_get_state(proxy);
    celviz_gpgpu_queue_t* queue = celviz_find_queue(proxy, queue_id);
    if (state == nullptr || queue == nullptr) {
        return CELVIZ_GPGPU_ERROR_BAD_QUEUE;
    }
    if (dst == nullptr && size != 0) {
        return CELVIZ_GPGPU_ERROR_BAD_DMA;
    }

    state->commands.emplace_back();
    auto& command = state->commands.back();
    command.sim = proxy->sim;
    command.status = celviz_make_status(
        queue_id, state->next_sequence++, CELVIZ_GPGPU_OPCODE_DMA_COPY, ventus_rtlsim_get_time(proxy->sim)
    );
    command.status.start_time = command.status.submit_time;

    celviz_submit_to_queue(queue);
    state->metrics.commands_submitted++;
    state->metrics.dma_copies++;

    celviz_gpgpu_error_t injected_error = CELVIZ_GPGPU_ERROR_OK;
    uint64_t injected_fault_address = 0;
    if (celviz_take_injected_error(state, queue_id, &injected_error, &injected_fault_address)) {
        celviz_finish_command(
            state, proxy, &command, CELVIZ_GPGPU_COMMAND_ERROR, injected_error,
            ventus_rtlsim_get_time(proxy->sim), injected_fault_address
        );
        if (out_status != nullptr) {
            *out_status = command.status;
        }
        return injected_error;
    }

    bool ok = ventus_rtlsim_pmemcpy_d2h(proxy->sim, dst, src, size);
    if (ok) {
        state->metrics.bytes_read += size;
        state->metrics.bytes_moved += size;
    }
    celviz_finish_command(
        state, proxy, &command, ok ? CELVIZ_GPGPU_COMMAND_COMPLETE : CELVIZ_GPGPU_COMMAND_ERROR,
        ok ? CELVIZ_GPGPU_ERROR_OK : CELVIZ_GPGPU_ERROR_MMU_FAULT, ventus_rtlsim_get_time(proxy->sim)
    );
    if (out_status != nullptr) {
        *out_status = command.status;
    }
    return ok ? CELVIZ_GPGPU_ERROR_OK : CELVIZ_GPGPU_ERROR_MMU_FAULT;
}

extern "C" celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_submit_fill(
    celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id, uint64_t dst, uint32_t pattern_u32, uint64_t size,
    celviz_gpgpu_command_status_record_t* out_status
) {
    celviz_gpgpu_runtime_state_t* state = celviz_get_state(proxy);
    celviz_gpgpu_queue_t* queue = celviz_find_queue(proxy, queue_id);
    if (state == nullptr || queue == nullptr) {
        return CELVIZ_GPGPU_ERROR_BAD_QUEUE;
    }

    state->commands.emplace_back();
    auto& command = state->commands.back();
    command.sim = proxy->sim;
    command.status = celviz_make_status(
        queue_id, state->next_sequence++, CELVIZ_GPGPU_OPCODE_DMA_FILL, ventus_rtlsim_get_time(proxy->sim)
    );
    command.status.start_time = command.status.submit_time;

    celviz_submit_to_queue(queue);
    state->metrics.commands_submitted++;
    state->metrics.dma_fills++;

    celviz_gpgpu_error_t injected_error = CELVIZ_GPGPU_ERROR_OK;
    uint64_t injected_fault_address = 0;
    if (celviz_take_injected_error(state, queue_id, &injected_error, &injected_fault_address)) {
        celviz_finish_command(
            state, proxy, &command, CELVIZ_GPGPU_COMMAND_ERROR, injected_error,
            ventus_rtlsim_get_time(proxy->sim), injected_fault_address
        );
        if (out_status != nullptr) {
            *out_status = command.status;
        }
        return injected_error;
    }

    std::vector<uint8_t> data(size);
    for (uint64_t i = 0; i < size; ++i) {
        data[i] = static_cast<uint8_t>((pattern_u32 >> ((i % 4) * 8)) & 0xffu);
    }

    bool ok = ventus_rtlsim_pmemcpy_h2d(proxy->sim, dst, data.data(), size);
    if (ok) {
        state->metrics.bytes_written += size;
        state->metrics.bytes_moved += size;
    }
    celviz_finish_command(
        state, proxy, &command, ok ? CELVIZ_GPGPU_COMMAND_COMPLETE : CELVIZ_GPGPU_COMMAND_ERROR,
        ok ? CELVIZ_GPGPU_ERROR_OK : CELVIZ_GPGPU_ERROR_MMU_FAULT, ventus_rtlsim_get_time(proxy->sim)
    );
    if (out_status != nullptr) {
        *out_status = command.status;
    }
    return ok ? CELVIZ_GPGPU_ERROR_OK : CELVIZ_GPGPU_ERROR_MMU_FAULT;
}

extern "C" celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_inject_next_error(
    celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id, celviz_gpgpu_error_t error,
    uint64_t fault_address
) {
    celviz_gpgpu_runtime_state_t* state = celviz_get_state(proxy);
    if (state == nullptr || celviz_find_queue(proxy, queue_id) == nullptr) {
        return CELVIZ_GPGPU_ERROR_BAD_QUEUE;
    }
    state->inject_next_error = true;
    state->inject_queue_id = queue_id;
    state->inject_error = error == CELVIZ_GPGPU_ERROR_OK ? CELVIZ_GPGPU_ERROR_INJECTED : error;
    state->inject_fault_address = fault_address;
    return CELVIZ_GPGPU_ERROR_OK;
}

extern "C" celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_submit_fault(
    celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id, celviz_gpgpu_error_t error,
    uint64_t fault_address, celviz_gpgpu_command_status_record_t* out_status
) {
    celviz_gpgpu_runtime_state_t* state = celviz_get_state(proxy);
    celviz_gpgpu_queue_t* queue = celviz_find_queue(proxy, queue_id);
    if (state == nullptr || queue == nullptr) {
        return CELVIZ_GPGPU_ERROR_BAD_QUEUE;
    }

    celviz_gpgpu_error_t fault_error = error == CELVIZ_GPGPU_ERROR_OK ? CELVIZ_GPGPU_ERROR_INJECTED : error;
    state->commands.emplace_back();
    auto& command = state->commands.back();
    command.sim = proxy->sim;
    command.status = celviz_make_status(
        queue_id, state->next_sequence++, CELVIZ_GPGPU_OPCODE_FAULT, ventus_rtlsim_get_time(proxy->sim)
    );
    command.status.start_time = command.status.submit_time;

    celviz_submit_to_queue(queue);
    state->metrics.commands_submitted++;
    celviz_finish_command(
        state, proxy, &command, CELVIZ_GPGPU_COMMAND_ERROR, fault_error,
        ventus_rtlsim_get_time(proxy->sim), fault_address
    );
    if (out_status != nullptr) {
        *out_status = command.status;
    }
    return fault_error;
}

extern "C" celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_step(
    celviz_gpgpu_runtime_proxy_t* proxy, celviz_gpgpu_event_status_t* out_event
) {
    celviz_gpgpu_runtime_state_t* state = celviz_get_state(proxy);
    if (state == nullptr) {
        return CELVIZ_GPGPU_ERROR_BAD_QUEUE;
    }

    celviz_reset_event(&state->last_event);
    celviz_mark_submitted_commands_running(state, ventus_rtlsim_get_time(proxy->sim));
    const ventus_rtlsim_step_result_t* step = ventus_rtlsim_step(proxy->sim);
    uint64_t time = ventus_rtlsim_get_time(proxy->sim);
    state->metrics.rtlsim_time = time;

    celviz_gpgpu_error_t result = CELVIZ_GPGPU_ERROR_OK;
    if (step != nullptr && step->error) {
        celviz_fail_nonterminal_commands(
            state, proxy, CELVIZ_GPGPU_COMMAND_ERROR, CELVIZ_GPGPU_ERROR_RTLSIM_FATAL, time
        );
        result = CELVIZ_GPGPU_ERROR_RTLSIM_FATAL;
    } else if (step != nullptr && step->time_exceed) {
        celviz_fail_nonterminal_commands(
            state, proxy, CELVIZ_GPGPU_COMMAND_TIMEOUT, CELVIZ_GPGPU_ERROR_RTLSIM_TIME_EXCEEDED, time
        );
        result = CELVIZ_GPGPU_ERROR_RTLSIM_TIME_EXCEEDED;
    } else if (step != nullptr && step->idle) {
        for (auto& command : state->commands) {
            if (!celviz_gpgpu_command_status_is_terminal(command.status.status)) {
                celviz_finish_command(
                    state, proxy, &command, CELVIZ_GPGPU_COMMAND_COMPLETE, CELVIZ_GPGPU_ERROR_OK, time
                );
            }
        }
    }

    if (out_event != nullptr) {
        *out_event = state->last_event;
    }
    return result;
}

extern "C" bool celviz_gpgpu_runtime_proxy_get_command_status(
    const celviz_gpgpu_runtime_proxy_t* proxy, uint32_t queue_id, uint64_t sequence,
    celviz_gpgpu_command_status_record_t* out_status
) {
    const celviz_gpgpu_runtime_state_t* state = celviz_get_state_const(proxy);
    if (state == nullptr || out_status == nullptr || celviz_find_queue_const(proxy, queue_id) == nullptr) {
        return false;
    }
    for (const auto& command : state->commands) {
        if (command.status.queue_id == queue_id && command.status.sequence == sequence) {
            *out_status = command.status;
            return true;
        }
    }
    return false;
}

extern "C" bool celviz_gpgpu_runtime_proxy_get_last_event(
    const celviz_gpgpu_runtime_proxy_t* proxy, celviz_gpgpu_event_status_t* out_event
) {
    const celviz_gpgpu_runtime_state_t* state = celviz_get_state_const(proxy);
    if (state == nullptr || out_event == nullptr) {
        return false;
    }
    *out_event = state->last_event;
    return true;
}

extern "C" bool celviz_gpgpu_runtime_proxy_get_metrics(
    const celviz_gpgpu_runtime_proxy_t* proxy, celviz_gpgpu_runtime_metrics_t* out_metrics
) {
    const celviz_gpgpu_runtime_state_t* state = celviz_get_state_const(proxy);
    if (state == nullptr || out_metrics == nullptr) {
        return false;
    }
    *out_metrics = state->metrics;
    if (proxy->sim != nullptr) {
        out_metrics->rtlsim_time = ventus_rtlsim_get_time(proxy->sim);
    }
    return true;
}

extern "C" bool celviz_gpgpu_runtime_proxy_reset_metrics(celviz_gpgpu_runtime_proxy_t* proxy) {
    celviz_gpgpu_runtime_state_t* state = celviz_get_state(proxy);
    if (state == nullptr) {
        return false;
    }
    state->metrics = {};
    state->metrics.rtlsim_time = ventus_rtlsim_get_time(proxy->sim);
    return true;
}

extern "C" uint64_t celviz_gpgpu_runtime_proxy_get_fence_value(const celviz_gpgpu_runtime_proxy_t* proxy) {
    const celviz_gpgpu_runtime_state_t* state = celviz_get_state_const(proxy);
    return state == nullptr ? 0 : state->fence_value;
}

extern "C" bool celviz_gpgpu_runtime_proxy_get_named_fence_value(
    const celviz_gpgpu_runtime_proxy_t* proxy, const char* fence_name, uint64_t* out_fence_value
) {
    const celviz_gpgpu_runtime_state_t* state = celviz_get_state_const(proxy);
    if (state == nullptr || fence_name == nullptr || fence_name[0] == '\0' || out_fence_value == nullptr) {
        return false;
    }
    auto it = state->named_fences.find(fence_name);
    *out_fence_value = it == state->named_fences.end() ? 0 : it->second;
    return true;
}

extern "C" celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_signal_fence(
    celviz_gpgpu_runtime_proxy_t* proxy, uint64_t fence_value, celviz_gpgpu_event_status_t* out_event
) {
    celviz_gpgpu_runtime_state_t* state = celviz_get_state(proxy);
    if (state == nullptr) {
        return CELVIZ_GPGPU_ERROR_BAD_QUEUE;
    }
    state->fence_value = std::max(state->fence_value, fence_value);
    state->metrics.fence_signals++;
    celviz_reset_event(&state->last_event);
    state->last_event.event_flags = CELVIZ_GPGPU_EVENT_COMMAND_COMPLETE;
    state->last_event.command.status = CELVIZ_GPGPU_COMMAND_COMPLETE;
    state->last_event.command.end_time = ventus_rtlsim_get_time(proxy->sim);
    if (out_event != nullptr) {
        *out_event = state->last_event;
    }
    return CELVIZ_GPGPU_ERROR_OK;
}

extern "C" celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_signal_named_fence(
    celviz_gpgpu_runtime_proxy_t* proxy, const char* fence_name, uint64_t fence_value,
    celviz_gpgpu_event_status_t* out_event
) {
    celviz_gpgpu_runtime_state_t* state = celviz_get_state(proxy);
    if (state == nullptr || fence_name == nullptr || fence_name[0] == '\0') {
        return CELVIZ_GPGPU_ERROR_BAD_QUEUE;
    }
    state->named_fences[fence_name] = std::max(state->named_fences[fence_name], fence_value);
    state->fence_value = std::max(state->fence_value, fence_value);
    state->metrics.fence_signals++;
    celviz_reset_event(&state->last_event);
    state->last_event.event_flags = CELVIZ_GPGPU_EVENT_COMMAND_COMPLETE;
    state->last_event.command.status = CELVIZ_GPGPU_COMMAND_COMPLETE;
    state->last_event.command.end_time = ventus_rtlsim_get_time(proxy->sim);
    if (out_event != nullptr) {
        *out_event = state->last_event;
    }
    return CELVIZ_GPGPU_ERROR_OK;
}

extern "C" celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_wait_fence(
    celviz_gpgpu_runtime_proxy_t* proxy, uint64_t fence_value, uint64_t max_steps,
    celviz_gpgpu_event_status_t* out_event
) {
    celviz_gpgpu_runtime_state_t* state = celviz_get_state(proxy);
    if (state == nullptr) {
        return CELVIZ_GPGPU_ERROR_BAD_QUEUE;
    }

    state->metrics.fence_waits++;
    uint64_t steps = 0;
    while (state->fence_value < fence_value && steps < max_steps) {
        celviz_gpgpu_error_t step_error = celviz_gpgpu_runtime_proxy_step(proxy, out_event);
        if (step_error != CELVIZ_GPGPU_ERROR_OK) {
            return step_error;
        }
        steps++;
    }

    if (state->fence_value < fence_value) {
        state->metrics.error_interrupts++;
        celviz_reset_event(&state->last_event);
        state->last_event.event_flags = CELVIZ_GPGPU_EVENT_WATCHDOG;
        state->last_event.command.status = CELVIZ_GPGPU_COMMAND_TIMEOUT;
        state->last_event.command.error = CELVIZ_GPGPU_ERROR_FENCE_WAIT;
        state->last_event.command.end_time = ventus_rtlsim_get_time(proxy->sim);
        if (out_event != nullptr) {
            *out_event = state->last_event;
        }
        return CELVIZ_GPGPU_ERROR_FENCE_WAIT;
    }
    if (out_event != nullptr) {
        *out_event = state->last_event;
    }
    return CELVIZ_GPGPU_ERROR_OK;
}

extern "C" celviz_gpgpu_error_t celviz_gpgpu_runtime_proxy_wait_named_fence(
    celviz_gpgpu_runtime_proxy_t* proxy, const char* fence_name, uint64_t fence_value, uint64_t max_steps,
    celviz_gpgpu_event_status_t* out_event
) {
    celviz_gpgpu_runtime_state_t* state = celviz_get_state(proxy);
    if (state == nullptr || fence_name == nullptr || fence_name[0] == '\0') {
        return CELVIZ_GPGPU_ERROR_BAD_QUEUE;
    }

    state->metrics.fence_waits++;
    uint64_t steps = 0;
    while (state->named_fences[fence_name] < fence_value && steps < max_steps) {
        celviz_gpgpu_error_t step_error = celviz_gpgpu_runtime_proxy_step(proxy, out_event);
        if (step_error != CELVIZ_GPGPU_ERROR_OK) {
            return step_error;
        }
        steps++;
    }

    if (state->named_fences[fence_name] < fence_value) {
        state->metrics.error_interrupts++;
        celviz_reset_event(&state->last_event);
        state->last_event.event_flags = CELVIZ_GPGPU_EVENT_WATCHDOG;
        state->last_event.command.status = CELVIZ_GPGPU_COMMAND_TIMEOUT;
        state->last_event.command.error = CELVIZ_GPGPU_ERROR_FENCE_WAIT;
        state->last_event.command.end_time = ventus_rtlsim_get_time(proxy->sim);
        if (out_event != nullptr) {
            *out_event = state->last_event;
        }
        return CELVIZ_GPGPU_ERROR_FENCE_WAIT;
    }
    if (out_event != nullptr) {
        *out_event = state->last_event;
    }
    return CELVIZ_GPGPU_ERROR_OK;
}
#ifdef ENABLE_GVM
extern "C" int fw_vt_dev_open() {
    return gvmref_vt_dev_open();
}
extern "C" int fw_vt_dev_close() {
    return gvmref_vt_dev_close();
}
extern "C" int fw_vt_buf_alloc(uint64_t size, uint64_t *vaddr, int BUF_TYPE, uint64_t taskID, uint64_t kernelID) {
    return gvmref_vt_buf_alloc(size, vaddr, BUF_TYPE, taskID, kernelID);
}
extern "C" int fw_vt_buf_free(uint64_t size, uint64_t *vaddr, uint64_t taskID, uint64_t kernelID) {
    return gvmref_vt_buf_free(size, vaddr, taskID, kernelID);
}
extern "C" int fw_vt_one_buf_free(uint64_t size, uint64_t *vaddr, uint64_t taskID, uint64_t kernelID) {
    return gvmref_vt_one_buf_free(size, vaddr, taskID, kernelID);
}
extern "C" int fw_vt_copy_to_dev(uint64_t dev_vaddr,const void *src_addr, uint64_t size, uint64_t taskID, uint64_t kernelID) {
    return gvmref_vt_copy_to_dev(dev_vaddr, src_addr, size, taskID, kernelID);
}
extern "C" int fw_vt_start(void* metaData, uint64_t taskID) {
    return gvmref_vt_start(metaData, taskID);
}
extern "C" int fw_vt_upload_kernel_file(const char* filename, int taskID) {
    return gvmref_vt_upload_kernel_file(filename, taskID);
}
#endif // ENABLE_GVM
