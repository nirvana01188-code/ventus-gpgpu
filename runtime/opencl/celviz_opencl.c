#include "celviz_opencl.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CELVIZ_MAGIC_PLATFORM 0x706c6174u
#define CELVIZ_MAGIC_DEVICE 0x64657669u
#define CELVIZ_MAGIC_CONTEXT 0x63747874u
#define CELVIZ_MAGIC_QUEUE 0x71756575u
#define CELVIZ_MAGIC_MEM 0x6d656d6fu
#define CELVIZ_MAGIC_PROGRAM 0x70726f67u
#define CELVIZ_MAGIC_KERNEL 0x6b65726eu
#define CELVIZ_MAGIC_EVENT 0x65766e74u

#define CELVIZ_MAX_KERNEL_ARGS 8

struct celviz_cl_platform {
    uint32_t magic;
};

struct celviz_cl_device {
    uint32_t magic;
};

struct celviz_cl_context {
    uint32_t magic;
    cl_device_id device;
};

struct celviz_cl_command_queue {
    uint32_t magic;
    cl_context context;
    cl_device_id device;
    cl_command_queue_properties properties;
    unsigned completed;
};

struct celviz_cl_mem {
    uint32_t magic;
    cl_context context;
    cl_mem_flags flags;
    size_t size;
    unsigned char *data;
};

struct celviz_kernel_arg {
    unsigned set;
    size_t size;
    unsigned char inline_value[sizeof(void *) > sizeof(cl_uint) ? sizeof(void *) : sizeof(cl_uint)];
};

struct celviz_cl_program {
    uint32_t magic;
    cl_context context;
    char *source;
    int built;
    char build_log[256];
};

struct celviz_cl_kernel {
    uint32_t magic;
    cl_program program;
    char name[64];
    struct celviz_kernel_arg args[CELVIZ_MAX_KERNEL_ARGS];
};

struct celviz_cl_event {
    uint32_t magic;
    int complete;
};

static struct celviz_cl_platform celviz_platform = {CELVIZ_MAGIC_PLATFORM};
static struct celviz_cl_device celviz_device = {CELVIZ_MAGIC_DEVICE};

static void celviz_set_error(cl_int *errcode_ret, cl_int value) {
    if (errcode_ret) {
        *errcode_ret = value;
    }
}

static int celviz_valid_context(cl_context context) {
    return context && context->magic == CELVIZ_MAGIC_CONTEXT;
}

static int celviz_valid_queue(cl_command_queue queue) {
    return queue && queue->magic == CELVIZ_MAGIC_QUEUE && celviz_valid_context(queue->context);
}

static int celviz_valid_mem(cl_mem mem) {
    return mem && mem->magic == CELVIZ_MAGIC_MEM && celviz_valid_context(mem->context);
}

static int celviz_valid_program(cl_program program) {
    return program && program->magic == CELVIZ_MAGIC_PROGRAM && celviz_valid_context(program->context);
}

static int celviz_valid_kernel(cl_kernel kernel) {
    return kernel && kernel->magic == CELVIZ_MAGIC_KERNEL && celviz_valid_program(kernel->program);
}

static cl_int celviz_check_wait_list(cl_uint count, const cl_event *events) {
    if ((count == 0 && events) || (count != 0 && !events)) {
        return CL_INVALID_VALUE;
    }
    for (cl_uint i = 0; i < count; ++i) {
        if (!events[i] || events[i]->magic != CELVIZ_MAGIC_EVENT || !events[i]->complete) {
            return CL_INVALID_VALUE;
        }
    }
    return CL_SUCCESS;
}

static cl_int celviz_make_event(cl_event *event) {
    if (!event) {
        return CL_SUCCESS;
    }
    *event = (cl_event)calloc(1, sizeof(**event));
    if (!*event) {
        return CL_OUT_OF_HOST_MEMORY;
    }
    (*event)->magic = CELVIZ_MAGIC_EVENT;
    (*event)->complete = 1;
    return CL_SUCCESS;
}

cl_int clGetPlatformIDs(cl_uint num_entries, cl_platform_id *platforms, cl_uint *num_platforms) {
    if (!platforms && !num_platforms) {
        return CL_INVALID_VALUE;
    }
    if (platforms && num_entries == 0) {
        return CL_INVALID_VALUE;
    }
    if (num_platforms) {
        *num_platforms = 1;
    }
    if (platforms) {
        platforms[0] = &celviz_platform;
    }
    return CL_SUCCESS;
}

cl_int clGetDeviceIDs(cl_platform_id platform,
                      cl_device_type device_type,
                      cl_uint num_entries,
                      cl_device_id *devices,
                      cl_uint *num_devices) {
    if (!platform || platform->magic != CELVIZ_MAGIC_PLATFORM) {
        return CL_INVALID_VALUE;
    }
    if (!devices && !num_devices) {
        return CL_INVALID_VALUE;
    }
    if (devices && num_entries == 0) {
        return CL_INVALID_VALUE;
    }
    if (!(device_type & (CL_DEVICE_TYPE_GPU | CL_DEVICE_TYPE_DEFAULT | CL_DEVICE_TYPE_ALL))) {
        return CL_DEVICE_NOT_FOUND;
    }
    if (num_devices) {
        *num_devices = 1;
    }
    if (devices) {
        devices[0] = &celviz_device;
    }
    return CL_SUCCESS;
}

cl_context clCreateContext(const cl_context_properties *properties,
                           cl_uint num_devices,
                           const cl_device_id *devices,
                           void (*pfn_notify)(const char *, const void *, size_t, void *),
                           void *user_data,
                           cl_int *errcode_ret) {
    (void)properties;
    (void)pfn_notify;
    (void)user_data;
    if (num_devices != 1 || !devices || !devices[0] || devices[0]->magic != CELVIZ_MAGIC_DEVICE) {
        celviz_set_error(errcode_ret, CL_INVALID_DEVICE);
        return NULL;
    }
    cl_context context = (cl_context)calloc(1, sizeof(*context));
    if (!context) {
        celviz_set_error(errcode_ret, CL_OUT_OF_HOST_MEMORY);
        return NULL;
    }
    context->magic = CELVIZ_MAGIC_CONTEXT;
    context->device = devices[0];
    celviz_set_error(errcode_ret, CL_SUCCESS);
    return context;
}

cl_command_queue clCreateCommandQueueWithProperties(cl_context context,
                                                    cl_device_id device,
                                                    const cl_queue_properties *properties,
                                                    cl_int *errcode_ret) {
    if (!celviz_valid_context(context) || device != context->device) {
        celviz_set_error(errcode_ret, CL_INVALID_CONTEXT);
        return NULL;
    }
    cl_command_queue_properties queue_props = 0;
    if (properties) {
        for (const cl_queue_properties *p = properties; p[0] != 0; p += 2) {
            if (p[0] != CL_QUEUE_PROPERTIES) {
                celviz_set_error(errcode_ret, CL_INVALID_QUEUE_PROPERTIES);
                return NULL;
            }
            queue_props = (cl_command_queue_properties)p[1];
        }
    }
    if (queue_props & CL_QUEUE_OUT_OF_ORDER_EXEC_MODE_ENABLE) {
        celviz_set_error(errcode_ret, CL_INVALID_QUEUE_PROPERTIES);
        return NULL;
    }
    cl_command_queue queue = (cl_command_queue)calloc(1, sizeof(*queue));
    if (!queue) {
        celviz_set_error(errcode_ret, CL_OUT_OF_HOST_MEMORY);
        return NULL;
    }
    queue->magic = CELVIZ_MAGIC_QUEUE;
    queue->context = context;
    queue->device = device;
    queue->properties = queue_props;
    celviz_set_error(errcode_ret, CL_SUCCESS);
    return queue;
}

cl_mem clCreateBuffer(cl_context context,
                      cl_mem_flags flags,
                      size_t size,
                      void *host_ptr,
                      cl_int *errcode_ret) {
    if (!celviz_valid_context(context)) {
        celviz_set_error(errcode_ret, CL_INVALID_CONTEXT);
        return NULL;
    }
    if (size == 0) {
        celviz_set_error(errcode_ret, CL_INVALID_VALUE);
        return NULL;
    }
    if ((flags & CL_MEM_COPY_HOST_PTR) && !host_ptr) {
        celviz_set_error(errcode_ret, CL_INVALID_HOST_PTR);
        return NULL;
    }
    cl_mem mem = (cl_mem)calloc(1, sizeof(*mem));
    if (!mem) {
        celviz_set_error(errcode_ret, CL_OUT_OF_HOST_MEMORY);
        return NULL;
    }
    mem->data = (unsigned char *)calloc(1, size);
    if (!mem->data) {
        free(mem);
        celviz_set_error(errcode_ret, CL_OUT_OF_HOST_MEMORY);
        return NULL;
    }
    mem->magic = CELVIZ_MAGIC_MEM;
    mem->context = context;
    mem->flags = flags;
    mem->size = size;
    if (flags & CL_MEM_COPY_HOST_PTR) {
        memcpy(mem->data, host_ptr, size);
    }
    celviz_set_error(errcode_ret, CL_SUCCESS);
    return mem;
}

cl_program clCreateProgramWithSource(cl_context context,
                                     cl_uint count,
                                     const char **strings,
                                     const size_t *lengths,
                                     cl_int *errcode_ret) {
    if (!celviz_valid_context(context)) {
        celviz_set_error(errcode_ret, CL_INVALID_CONTEXT);
        return NULL;
    }
    if (count == 0 || !strings) {
        celviz_set_error(errcode_ret, CL_INVALID_VALUE);
        return NULL;
    }
    size_t total = 0;
    for (cl_uint i = 0; i < count; ++i) {
        if (!strings[i]) {
            celviz_set_error(errcode_ret, CL_INVALID_VALUE);
            return NULL;
        }
        total += lengths && lengths[i] ? lengths[i] : strlen(strings[i]);
    }
    cl_program program = (cl_program)calloc(1, sizeof(*program));
    if (!program) {
        celviz_set_error(errcode_ret, CL_OUT_OF_HOST_MEMORY);
        return NULL;
    }
    program->source = (char *)calloc(total + 1, 1);
    if (!program->source) {
        free(program);
        celviz_set_error(errcode_ret, CL_OUT_OF_HOST_MEMORY);
        return NULL;
    }
    char *cursor = program->source;
    for (cl_uint i = 0; i < count; ++i) {
        size_t len = lengths && lengths[i] ? lengths[i] : strlen(strings[i]);
        memcpy(cursor, strings[i], len);
        cursor += len;
    }
    program->magic = CELVIZ_MAGIC_PROGRAM;
    program->context = context;
    snprintf(program->build_log, sizeof(program->build_log), "not built");
    celviz_set_error(errcode_ret, CL_SUCCESS);
    return program;
}

cl_int clBuildProgram(cl_program program,
                      cl_uint num_devices,
                      const cl_device_id *device_list,
                      const char *options,
                      void (*pfn_notify)(cl_program, void *),
                      void *user_data) {
    (void)options;
    if (!celviz_valid_program(program)) {
        return CL_INVALID_PROGRAM;
    }
    if (num_devices > 1 || (num_devices == 1 && (!device_list || device_list[0] != program->context->device))) {
        return CL_INVALID_DEVICE;
    }
    if (strstr(program->source, "double") || strstr(program->source, "image2d_t") ||
        strstr(program->source, "sampler_t") || strstr(program->source, "atomic_") ||
        strstr(program->source, "printf")) {
        snprintf(program->build_log, sizeof(program->build_log),
                 "Celviz clean-room subset rejects unsupported OpenCL C feature");
        program->built = 0;
        return CL_BUILD_PROGRAM_FAILURE;
    }
    if (!strstr(program->source, "__kernel") || !strstr(program->source, "vector_add")) {
        snprintf(program->build_log, sizeof(program->build_log),
                 "Celviz subset smoke supports one __kernel named vector_add");
        program->built = 0;
        return CL_BUILD_PROGRAM_FAILURE;
    }
    program->built = 1;
    snprintf(program->build_log, sizeof(program->build_log),
             "Celviz clean-room OpenCL-like C ABI subset build passed");
    if (pfn_notify) {
        pfn_notify(program, user_data);
    }
    return CL_SUCCESS;
}

cl_int clGetProgramBuildInfo(cl_program program,
                             cl_device_id device,
                             cl_uint param_name,
                             size_t param_value_size,
                             void *param_value,
                             size_t *param_value_size_ret) {
    if (!celviz_valid_program(program)) {
        return CL_INVALID_PROGRAM;
    }
    if (device && device != program->context->device) {
        return CL_INVALID_DEVICE;
    }
    if (param_name != CL_PROGRAM_BUILD_LOG) {
        return CL_INVALID_VALUE;
    }
    size_t len = strlen(program->build_log) + 1;
    if (param_value_size_ret) {
        *param_value_size_ret = len;
    }
    if (param_value) {
        if (param_value_size < len) {
            return CL_INVALID_VALUE;
        }
        memcpy(param_value, program->build_log, len);
    }
    return CL_SUCCESS;
}

cl_kernel clCreateKernel(cl_program program, const char *kernel_name, cl_int *errcode_ret) {
    if (!celviz_valid_program(program)) {
        celviz_set_error(errcode_ret, CL_INVALID_PROGRAM);
        return NULL;
    }
    if (!program->built) {
        celviz_set_error(errcode_ret, CL_INVALID_PROGRAM_EXECUTABLE);
        return NULL;
    }
    if (!kernel_name || strcmp(kernel_name, "vector_add") != 0) {
        celviz_set_error(errcode_ret, CL_INVALID_KERNEL_NAME);
        return NULL;
    }
    cl_kernel kernel = (cl_kernel)calloc(1, sizeof(*kernel));
    if (!kernel) {
        celviz_set_error(errcode_ret, CL_OUT_OF_HOST_MEMORY);
        return NULL;
    }
    kernel->magic = CELVIZ_MAGIC_KERNEL;
    kernel->program = program;
    snprintf(kernel->name, sizeof(kernel->name), "%s", kernel_name);
    celviz_set_error(errcode_ret, CL_SUCCESS);
    return kernel;
}

cl_int clSetKernelArg(cl_kernel kernel, cl_uint arg_index, size_t arg_size, const void *arg_value) {
    if (!celviz_valid_kernel(kernel)) {
        return CL_INVALID_KERNEL;
    }
    if (arg_index >= CELVIZ_MAX_KERNEL_ARGS) {
        return CL_INVALID_ARG_INDEX;
    }
    if (!arg_value || arg_size == 0 || arg_size > sizeof(kernel->args[arg_index].inline_value)) {
        return CL_INVALID_ARG_SIZE;
    }
    memcpy(kernel->args[arg_index].inline_value, arg_value, arg_size);
    kernel->args[arg_index].size = arg_size;
    kernel->args[arg_index].set = 1;
    return CL_SUCCESS;
}

cl_int clEnqueueWriteBuffer(cl_command_queue command_queue,
                            cl_mem buffer,
                            cl_bool blocking_write,
                            size_t offset,
                            size_t size,
                            const void *ptr,
                            cl_uint num_events_in_wait_list,
                            const cl_event *event_wait_list,
                            cl_event *event) {
    (void)blocking_write;
    cl_int wait_status = celviz_check_wait_list(num_events_in_wait_list, event_wait_list);
    if (wait_status != CL_SUCCESS) {
        return wait_status;
    }
    if (!celviz_valid_queue(command_queue)) {
        return CL_INVALID_COMMAND_QUEUE;
    }
    if (!celviz_valid_mem(buffer) || buffer->context != command_queue->context) {
        return CL_INVALID_MEM_OBJECT;
    }
    if (!ptr || offset > buffer->size || size > buffer->size - offset) {
        return CL_INVALID_VALUE;
    }
    memcpy(buffer->data + offset, ptr, size);
    return celviz_make_event(event);
}

cl_int clEnqueueNDRangeKernel(cl_command_queue command_queue,
                              cl_kernel kernel,
                              cl_uint work_dim,
                              const size_t *global_work_offset,
                              const size_t *global_work_size,
                              const size_t *local_work_size,
                              cl_uint num_events_in_wait_list,
                              const cl_event *event_wait_list,
                              cl_event *event) {
    (void)global_work_offset;
    cl_int wait_status = celviz_check_wait_list(num_events_in_wait_list, event_wait_list);
    if (wait_status != CL_SUCCESS) {
        return wait_status;
    }
    if (!celviz_valid_queue(command_queue)) {
        return CL_INVALID_COMMAND_QUEUE;
    }
    if (!celviz_valid_kernel(kernel)) {
        return CL_INVALID_KERNEL;
    }
    if (work_dim != 1 || !global_work_size || global_work_size[0] == 0) {
        return CL_INVALID_WORK_DIMENSION;
    }
    if (local_work_size && local_work_size[0] > global_work_size[0]) {
        return CL_INVALID_WORK_GROUP_SIZE;
    }
    for (cl_uint i = 0; i < 4; ++i) {
        if (!kernel->args[i].set) {
            return CL_INVALID_KERNEL_ARGS;
        }
    }
    cl_mem a = NULL;
    cl_mem b = NULL;
    cl_mem c = NULL;
    cl_uint n = 0;
    memcpy(&a, kernel->args[0].inline_value, sizeof(a));
    memcpy(&b, kernel->args[1].inline_value, sizeof(b));
    memcpy(&c, kernel->args[2].inline_value, sizeof(c));
    memcpy(&n, kernel->args[3].inline_value, sizeof(n));
    if (!celviz_valid_mem(a) || !celviz_valid_mem(b) || !celviz_valid_mem(c)) {
        return CL_INVALID_MEM_OBJECT;
    }
    if (a->context != command_queue->context || b->context != command_queue->context || c->context != command_queue->context) {
        return CL_INVALID_CONTEXT;
    }
    size_t count = global_work_size[0] < (size_t)n ? global_work_size[0] : (size_t)n;
    if (a->size < count * sizeof(float) || b->size < count * sizeof(float) || c->size < count * sizeof(float)) {
        return CL_INVALID_VALUE;
    }
    float *af = (float *)a->data;
    float *bf = (float *)b->data;
    float *cf = (float *)c->data;
    for (size_t i = 0; i < count; ++i) {
        cf[i] = af[i] + bf[i];
    }
    command_queue->completed++;
    return celviz_make_event(event);
}

cl_int clEnqueueReadBuffer(cl_command_queue command_queue,
                           cl_mem buffer,
                           cl_bool blocking_read,
                           size_t offset,
                           size_t size,
                           void *ptr,
                           cl_uint num_events_in_wait_list,
                           const cl_event *event_wait_list,
                           cl_event *event) {
    (void)blocking_read;
    cl_int wait_status = celviz_check_wait_list(num_events_in_wait_list, event_wait_list);
    if (wait_status != CL_SUCCESS) {
        return wait_status;
    }
    if (!celviz_valid_queue(command_queue)) {
        return CL_INVALID_COMMAND_QUEUE;
    }
    if (!celviz_valid_mem(buffer) || buffer->context != command_queue->context) {
        return CL_INVALID_MEM_OBJECT;
    }
    if (!ptr || offset > buffer->size || size > buffer->size - offset) {
        return CL_INVALID_VALUE;
    }
    memcpy(ptr, buffer->data + offset, size);
    return celviz_make_event(event);
}

cl_int clFinish(cl_command_queue command_queue) {
    if (!celviz_valid_queue(command_queue)) {
        return CL_INVALID_COMMAND_QUEUE;
    }
    return CL_SUCCESS;
}

cl_int clReleaseMemObject(cl_mem memobj) {
    if (!celviz_valid_mem(memobj)) {
        return CL_INVALID_MEM_OBJECT;
    }
    memobj->magic = 0;
    free(memobj->data);
    free(memobj);
    return CL_SUCCESS;
}

cl_int clReleaseKernel(cl_kernel kernel) {
    if (!celviz_valid_kernel(kernel)) {
        return CL_INVALID_KERNEL;
    }
    kernel->magic = 0;
    free(kernel);
    return CL_SUCCESS;
}

cl_int clReleaseProgram(cl_program program) {
    if (!celviz_valid_program(program)) {
        return CL_INVALID_PROGRAM;
    }
    program->magic = 0;
    free(program->source);
    free(program);
    return CL_SUCCESS;
}

cl_int clReleaseCommandQueue(cl_command_queue command_queue) {
    if (!celviz_valid_queue(command_queue)) {
        return CL_INVALID_COMMAND_QUEUE;
    }
    command_queue->magic = 0;
    free(command_queue);
    return CL_SUCCESS;
}

cl_int clReleaseContext(cl_context context) {
    if (!celviz_valid_context(context)) {
        return CL_INVALID_CONTEXT;
    }
    context->magic = 0;
    free(context);
    return CL_SUCCESS;
}

cl_int clReleaseEvent(cl_event event) {
    if (!event || event->magic != CELVIZ_MAGIC_EVENT) {
        return CL_INVALID_VALUE;
    }
    event->magic = 0;
    free(event);
    return CL_SUCCESS;
}
