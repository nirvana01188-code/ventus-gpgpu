__kernel void gemm(__global const float *a,
                   __global const float *b,
                   __global float *c,
                   uint m,
                   uint n,
                   uint k) {
  uint row = get_global_id(1);
  uint col = get_global_id(0);
  if (row < m && col < n) {
    float acc = 0.0f;
    for (uint i = 0; i < k; ++i) {
      acc = acc + a[row * k + i] * b[i * n + col];
    }
    c[row * n + col] = acc;
  }
}
