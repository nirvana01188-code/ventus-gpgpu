__kernel void image_filter(__global const uchar4 *src,
                           __global uchar4 *dst,
                           uint width,
                           uint height,
                           float gain) {
  uint x = get_global_id(0);
  uint y = get_global_id(1);
  if (x < width && y < height) {
    uint idx = y * width + x;
    uchar4 px = src[idx];
    dst[idx] = (uchar4)(px.x * gain, px.y * gain, px.z * gain, px.w);
  }
}
