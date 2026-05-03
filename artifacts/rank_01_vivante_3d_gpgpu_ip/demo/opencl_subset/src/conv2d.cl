__kernel void conv2d(__global const float *input,
                     __global const float *filter,
                     __global float *output,
                     uint width,
                     uint height) {
  uint x = get_global_id(0);
  uint y = get_global_id(1);
  if (x > 0 && y > 0 && x + 1 < width && y + 1 < height) {
    float acc = 0.0f;
    for (uint fy = 0; fy < 3; ++fy) {
      for (uint fx = 0; fx < 3; ++fx) {
        uint ix = x + fx - 1;
        uint iy = y + fy - 1;
        acc = acc + input[iy * width + ix] * filter[fy * 3 + fx];
      }
    }
    output[y * width + x] = acc;
  }
}
