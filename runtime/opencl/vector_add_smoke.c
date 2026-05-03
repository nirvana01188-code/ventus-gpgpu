#include "celviz_opencl.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#define CHECK_CL(call)                                                                      \
    do {                                                                                    \
        cl_int _status = (call);                                                            \
        if (_status != CL_SUCCESS) {                                                        \
            fprintf(stderr, "%s failed with %d at %s:%d\n", #call, _status, __FILE__,      \
                    __LINE__);                                                              \
            return 1;                                                                       \
        }                                                                                   \
    } while (0)

static const char *vector_add_source =
    "__kernel void vector_add(__global const float *a, __global const float *b, "
    "__global float *c, uint n) { size_t gid = get_global_id(0); if (gid < n) c[gid] = "
    "a[gid] + b[gid]; }";

int main(void) {
    enum { n = 256 };
    float a[n];
    float b[n];
    float c[n];
    for (cl_uint i = 0; i < n; ++i) {
        a[i] = (float)i * 0.5f;
        b[i] = 100.0f - (float)i * 0.25f;
        c[i] = 0.0f;
    }

    cl_int err = CL_SUCCESS;
    cl_platform_id platform = NULL;
    cl_device_id device = NULL;
    CHECK_CL(clGetPlatformIDs(1, &platform, NULL));
    CHECK_CL(clGetDeviceIDs(platform, CL_DEVICE_TYPE_GPU, 1, &device, NULL));

    cl_context context = clCreateContext(NULL, 1, &device, NULL, NULL, &err);
    CHECK_CL(err);
    cl_command_queue queue = clCreateCommandQueueWithProperties(context, device, NULL, &err);
    CHECK_CL(err);

    cl_mem a_buf = clCreateBuffer(context, CL_MEM_READ_ONLY, sizeof(a), NULL, &err);
    CHECK_CL(err);
    cl_mem b_buf = clCreateBuffer(context, CL_MEM_READ_ONLY, sizeof(b), NULL, &err);
    CHECK_CL(err);
    cl_mem c_buf = clCreateBuffer(context, CL_MEM_WRITE_ONLY, sizeof(c), NULL, &err);
    CHECK_CL(err);

    CHECK_CL(clEnqueueWriteBuffer(queue, a_buf, CL_TRUE, 0, sizeof(a), a, 0, NULL, NULL));
    CHECK_CL(clEnqueueWriteBuffer(queue, b_buf, CL_TRUE, 0, sizeof(b), b, 0, NULL, NULL));

    cl_program program = clCreateProgramWithSource(context, 1, &vector_add_source, NULL, &err);
    CHECK_CL(err);
    CHECK_CL(clBuildProgram(program, 1, &device, NULL, NULL, NULL));
    cl_kernel kernel = clCreateKernel(program, "vector_add", &err);
    CHECK_CL(err);

    cl_uint count = n;
    CHECK_CL(clSetKernelArg(kernel, 0, sizeof(a_buf), &a_buf));
    CHECK_CL(clSetKernelArg(kernel, 1, sizeof(b_buf), &b_buf));
    CHECK_CL(clSetKernelArg(kernel, 2, sizeof(c_buf), &c_buf));
    CHECK_CL(clSetKernelArg(kernel, 3, sizeof(count), &count));

    size_t global = n;
    cl_event kernel_done = NULL;
    CHECK_CL(clEnqueueNDRangeKernel(queue, kernel, 1, NULL, &global, NULL, 0, NULL, &kernel_done));
    CHECK_CL(clEnqueueReadBuffer(queue, c_buf, CL_TRUE, 0, sizeof(c), c, 1, &kernel_done, NULL));
    CHECK_CL(clFinish(queue));

    double max_abs_error = 0.0;
    for (cl_uint i = 0; i < n; ++i) {
        double expected = (double)a[i] + (double)b[i];
        double err_abs = fabs((double)c[i] - expected);
        if (err_abs > max_abs_error) {
            max_abs_error = err_abs;
        }
        if (err_abs > 0.00001) {
            fprintf(stderr, "mismatch at %u: got %.8f expected %.8f\n", i, c[i], (float)expected);
            return 2;
        }
    }

    CHECK_CL(clReleaseEvent(kernel_done));
    CHECK_CL(clReleaseKernel(kernel));
    CHECK_CL(clReleaseProgram(program));
    CHECK_CL(clReleaseMemObject(a_buf));
    CHECK_CL(clReleaseMemObject(b_buf));
    CHECK_CL(clReleaseMemObject(c_buf));
    CHECK_CL(clReleaseCommandQueue(queue));
    CHECK_CL(clReleaseContext(context));

    printf("vector_add_smoke: pass elements=%u max_abs_error=%.8f\n", (unsigned)n, max_abs_error);
    return 0;
}
