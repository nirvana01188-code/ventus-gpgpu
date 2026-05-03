#ifndef CELVIZ_OPENCL_H
#define CELVIZ_OPENCL_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef int32_t cl_int;
typedef uint32_t cl_uint;
typedef uint64_t cl_ulong;
typedef cl_ulong cl_bitfield;
typedef cl_bitfield cl_device_type;
typedef cl_bitfield cl_mem_flags;
typedef cl_bitfield cl_command_queue_properties;
typedef intptr_t cl_context_properties;
typedef intptr_t cl_queue_properties;
typedef intptr_t cl_bool;

typedef struct celviz_cl_platform *cl_platform_id;
typedef struct celviz_cl_device *cl_device_id;
typedef struct celviz_cl_context *cl_context;
typedef struct celviz_cl_command_queue *cl_command_queue;
typedef struct celviz_cl_mem *cl_mem;
typedef struct celviz_cl_program *cl_program;
typedef struct celviz_cl_kernel *cl_kernel;
typedef struct celviz_cl_event *cl_event;

#define CL_FALSE 0
#define CL_TRUE 1

#define CL_SUCCESS 0
#define CL_DEVICE_NOT_FOUND -1
#define CL_INVALID_VALUE -30
#define CL_INVALID_DEVICE -33
#define CL_INVALID_CONTEXT -34
#define CL_INVALID_COMMAND_QUEUE -36
#define CL_INVALID_MEM_OBJECT -38
#define CL_INVALID_BINARY -42
#define CL_INVALID_BUILD_OPTIONS -43
#define CL_INVALID_PROGRAM -44
#define CL_INVALID_PROGRAM_EXECUTABLE -45
#define CL_INVALID_KERNEL_NAME -46
#define CL_INVALID_KERNEL -48
#define CL_INVALID_ARG_INDEX -49
#define CL_INVALID_ARG_VALUE -50
#define CL_INVALID_ARG_SIZE -51
#define CL_INVALID_KERNEL_ARGS -52
#define CL_INVALID_WORK_DIMENSION -53
#define CL_INVALID_WORK_GROUP_SIZE -54
#define CL_INVALID_HOST_PTR -37
#define CL_INVALID_QUEUE_PROPERTIES -35
#define CL_BUILD_PROGRAM_FAILURE -11
#define CL_OUT_OF_HOST_MEMORY -6

#define CL_DEVICE_TYPE_DEFAULT (1ULL << 0)
#define CL_DEVICE_TYPE_GPU (1ULL << 2)
#define CL_DEVICE_TYPE_ALL 0xFFFFFFFFULL

#define CL_MEM_READ_WRITE (1ULL << 0)
#define CL_MEM_WRITE_ONLY (1ULL << 1)
#define CL_MEM_READ_ONLY (1ULL << 2)
#define CL_MEM_COPY_HOST_PTR (1ULL << 5)

#define CL_QUEUE_OUT_OF_ORDER_EXEC_MODE_ENABLE (1ULL << 0)
#define CL_QUEUE_PROFILING_ENABLE (1ULL << 1)
#define CL_QUEUE_PROPERTIES 0x1093

#define CL_PROGRAM_BUILD_LOG 0x1183

cl_int clGetPlatformIDs(cl_uint num_entries,
                        cl_platform_id *platforms,
                        cl_uint *num_platforms);
cl_int clGetDeviceIDs(cl_platform_id platform,
                      cl_device_type device_type,
                      cl_uint num_entries,
                      cl_device_id *devices,
                      cl_uint *num_devices);
cl_context clCreateContext(const cl_context_properties *properties,
                           cl_uint num_devices,
                           const cl_device_id *devices,
                           void (*pfn_notify)(const char *, const void *, size_t, void *),
                           void *user_data,
                           cl_int *errcode_ret);
cl_command_queue clCreateCommandQueueWithProperties(cl_context context,
                                                    cl_device_id device,
                                                    const cl_queue_properties *properties,
                                                    cl_int *errcode_ret);
cl_mem clCreateBuffer(cl_context context,
                      cl_mem_flags flags,
                      size_t size,
                      void *host_ptr,
                      cl_int *errcode_ret);
cl_program clCreateProgramWithSource(cl_context context,
                                     cl_uint count,
                                     const char **strings,
                                     const size_t *lengths,
                                     cl_int *errcode_ret);
cl_int clBuildProgram(cl_program program,
                      cl_uint num_devices,
                      const cl_device_id *device_list,
                      const char *options,
                      void (*pfn_notify)(cl_program, void *),
                      void *user_data);
cl_int clGetProgramBuildInfo(cl_program program,
                             cl_device_id device,
                             cl_uint param_name,
                             size_t param_value_size,
                             void *param_value,
                             size_t *param_value_size_ret);
cl_kernel clCreateKernel(cl_program program,
                         const char *kernel_name,
                         cl_int *errcode_ret);
cl_int clSetKernelArg(cl_kernel kernel,
                      cl_uint arg_index,
                      size_t arg_size,
                      const void *arg_value);
cl_int clEnqueueWriteBuffer(cl_command_queue command_queue,
                            cl_mem buffer,
                            cl_bool blocking_write,
                            size_t offset,
                            size_t size,
                            const void *ptr,
                            cl_uint num_events_in_wait_list,
                            const cl_event *event_wait_list,
                            cl_event *event);
cl_int clEnqueueNDRangeKernel(cl_command_queue command_queue,
                              cl_kernel kernel,
                              cl_uint work_dim,
                              const size_t *global_work_offset,
                              const size_t *global_work_size,
                              const size_t *local_work_size,
                              cl_uint num_events_in_wait_list,
                              const cl_event *event_wait_list,
                              cl_event *event);
cl_int clEnqueueReadBuffer(cl_command_queue command_queue,
                           cl_mem buffer,
                           cl_bool blocking_read,
                           size_t offset,
                           size_t size,
                           void *ptr,
                           cl_uint num_events_in_wait_list,
                           const cl_event *event_wait_list,
                           cl_event *event);
cl_int clFinish(cl_command_queue command_queue);
cl_int clReleaseMemObject(cl_mem memobj);
cl_int clReleaseKernel(cl_kernel kernel);
cl_int clReleaseProgram(cl_program program);
cl_int clReleaseCommandQueue(cl_command_queue command_queue);
cl_int clReleaseContext(cl_context context);
cl_int clReleaseEvent(cl_event event);

#ifdef __cplusplus
}
#endif

#endif
