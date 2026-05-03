package cta

import chisel3._
import chisel3.util._
import top.parameters.{CTA_SCHE_CONFIG => CONFIG}

/** IO Bundle: CTA information
 *  Data producer: host
 *  Data consumer: allocator
 *
 *  Information which is related to resource occupancy
 *  should be passed to the allocator.
 */
trait ctainfo_host_to_alloc extends Bundle {
  // num_wg_slot = 1 constant, one wg always occupies one slot
  val num_wf = UInt(log2Ceil(CONFIG.WG.NUM_WF_MAX+1).W)       // Number of wavefront in this cta
  val num_sgpr = UInt(log2Ceil(CONFIG.WG.NUM_SGPR_MAX+1).W)   // Number of sgpr used by this cta
  val num_vgpr = UInt(log2Ceil(CONFIG.WG.NUM_VGPR_MAX+1).W)   // Number of vgpr used by this cta
  val num_lds = UInt(log2Ceil(CONFIG.WG.NUM_LDS_MAX+1).W)     // Number of Local  Data Share used by this cta
}

/** IO Bundle: CTA information
 *  Data producer: host
 *  Data consumer: CU interface
 *
 *  Information which is related to splitting wg into wf
 */
trait ctainfo_host_to_cuinterface extends Bundle {
  val num_sgpr_per_wf = UInt(log2Ceil(CONFIG.WG.NUM_SGPR_MAX+1).W)      // Number of sgpr used by each wf in this wg
  val num_vgpr_per_wf = UInt(log2Ceil(CONFIG.WG.NUM_VGPR_MAX+1).W)      // Number of vgpr used by each wf in this wg
  val num_pds_per_wf = UInt(log2Ceil(CONFIG.WG.NUM_PDS_MAX+1).W)        // Number of pds  used by each wf in this wg
}

/** IO Bundle: CTA information
 *  Data producer: allocator
 *  Data consumer: CU interface
 *
 *  Information which is related to splitting wg into wf
 */
trait ctainfo_alloc_to_cuinterface extends Bundle {
  val cu_id = UInt(log2Ceil(CONFIG.GPU.NUM_CU).W)
  val wg_slot_id = UInt(log2Ceil(CONFIG.GPU.NUM_WG_SLOT).W)
  val num_wf = UInt(log2Ceil(CONFIG.WG.NUM_WF_MAX+1).W)                 // Number of wavefront in this cta
  val lds_dealloc_en = Bool()   // if LDS needs dealloc. When num_lds==0, lds do not need dealloc
  val sgpr_dealloc_en = Bool()
  val vgpr_dealloc_en = Bool()
}

/** IO Bundle: CTA information
 *  Data producer: allocator
 *  Data consumer: CU
 *
 *  Information which is related to code execution
 *  These are **WG** sgpr/vgpr/lds base address
 *  CU-interface may update them into **WF** sgpr/vgpr/lds base address
 */
trait ctainfo_alloc_to_cu extends Bundle {
  val sgpr_base = UInt(log2Ceil(CONFIG.WG.NUM_SGPR_MAX).W)            // sgpr base address (initial WG, later WF)
  val vgpr_base = UInt(log2Ceil(CONFIG.WG.NUM_VGPR_MAX).W)            // vgpr base address (initial WG, later WF)
  val lds_base = UInt(log2Ceil(CONFIG.WG.NUM_LDS_MAX).W)             // lds  base address (initial WG, later WF)
}

/** IO Bundle: CTA information
 *  Data producer: host
 *  Data consumer: CU
 *
 *  Information which is related code execution
 *  It will be passed on to CU later
 *  Some Information may be updated by CU-interface during splitting wg into wf
 */
trait ctainfo_host_to_cu extends Bundle {
  val num_thread_per_wf = UInt(log2Ceil(CONFIG.WG.NUM_THREAD_MAX+1).W)// Number of thread in each wf
  //val num_gds = UInt(log2Ceil(CONFIG.WG.NUM_GDS_MAX+1).W)           // Number of Global Data Share used by this WG
  val gds_base = UInt(CONFIG.GPU.MEM_ADDR_WIDTH)                      // GDS base address of this WG
  val pds_base = UInt(CONFIG.GPU.MEM_ADDR_WIDTH)                      // PDS base addr of this WG, convert to WF base addr in CUinterface
  val start_pc = UInt(CONFIG.GPU.MEM_ADDR_WIDTH)                      // Program start pc address
  val csr_kernel = UInt(CONFIG.GPU.MEM_ADDR_WIDTH)                    // Meta-data base address
  val num_wg_x = UInt(log2Ceil(CONFIG.WG.NUM_WG_DIM_MAX+1).W)         // Number of wg in x-dimension in this kernel
  val num_wg_y = UInt(log2Ceil(CONFIG.WG.NUM_WG_DIM_MAX+1).W)         // Number of wg in y-dimension in this kernel
  val num_wg_z = UInt(log2Ceil(CONFIG.WG.NUM_WG_DIM_MAX+1).W)         // Number of wg in z-dimension in this kernel
  val asid_kernel = if(CONFIG.GPU.MMU_ENABLE) Some(UInt(CONFIG.GPU.ASID_WIDTH)) else None // Virtual memory space ID
}

/** IO between CU-interface and CU
 */
class io_cuinterface2cu extends Bundle with ctainfo_host_to_cu with ctainfo_alloc_to_cu {
  val wg_id = UInt(CONFIG.WG.WG_ID_WIDTH)
  val wf_tag = UInt(CONFIG.WG.WF_TAG_WIDTH)
  val num_wf = UInt(log2Ceil(CONFIG.WG.NUM_WF_MAX+1).W)                 // Number of wavefront in this cta
}
class io_cu2cuinterface extends Bundle {
  val wf_tag = UInt(CONFIG.WG.WF_TAG_WIDTH)
  //val wg_id = if(CONFIG.DEBUG) Some(UInt(CONFIG.WG.WG_ID_WIDTH)) else None
}

/** IO between host and wg-buffer
 */
class io_host2cta extends Bundle with ctainfo_host_to_alloc with ctainfo_host_to_cuinterface with ctainfo_host_to_cu {
  val wg_id = UInt(CONFIG.WG.WG_ID_WIDTH)
}
class io_cta2host extends Bundle {
  val wg_id = UInt(CONFIG.WG.WG_ID_WIDTH)
  val cu_id = UInt(log2Ceil(CONFIG.GPU.NUM_CU).W)   // For CTA schedule strategy research
}

class io_cta_scheduler_celviz_debug(val NUM_CU: Int) extends Bundle {
  val host_wg_accepted = Bool()
  val host_wg_stalled = Bool()
  val host_wg_done = Bool()
  val host_wg_done_stalled = Bool()
  val wgbuffer_alloc_dispatch = Bool()
  val wgbuffer_alloc_stalled = Bool()
  val alloc_result_accepted = Bool()
  val alloc_result_rejected = Bool()
  val cuinterface_wg_enqueued = Bool()
  val cuinterface_wg_enqueue_stalled = Bool()
  val cu_wf_dispatch_fire = UInt(NUM_CU.W)
  val cu_wf_dispatch_stalled = UInt(NUM_CU.W)
  val cu_wf_done_fire = UInt(NUM_CU.W)
  val cu_wf_done_stalled = UInt(NUM_CU.W)
  val rt_alloc_blocked = Bool()
  val rt_dealloc_blocked = Bool()
  val rt_wg_result_blocked = Bool()
  val resource_blocked_mask = UInt(4.W)
  val host_wg_accepted_count = UInt(32.W)
  val host_wg_stalled_cycle_count = UInt(32.W)
  val host_wg_done_count = UInt(32.W)
  val host_wg_done_stalled_cycle_count = UInt(32.W)
  val wgbuffer_alloc_dispatch_count = UInt(32.W)
  val wgbuffer_alloc_stalled_cycle_count = UInt(32.W)
  val alloc_result_accepted_count = UInt(32.W)
  val alloc_result_rejected_count = UInt(32.W)
  val cuinterface_wg_enqueued_count = UInt(32.W)
  val cuinterface_wg_enqueue_stalled_cycle_count = UInt(32.W)
  val cu_wf_dispatch_fire_count = Vec(NUM_CU, UInt(32.W))
  val cu_wf_dispatch_fire_total_count = UInt(32.W)
  val cu_wf_dispatch_stalled_cycle_count = Vec(NUM_CU, UInt(32.W))
  val cu_wf_dispatch_stalled_total_cycle_count = UInt(32.W)
  val cu_wf_done_fire_count = Vec(NUM_CU, UInt(32.W))
  val cu_wf_done_fire_total_count = UInt(32.W)
  val cu_wf_done_stalled_cycle_count = Vec(NUM_CU, UInt(32.W))
  val cu_wf_done_stalled_total_cycle_count = UInt(32.W)
  val alloc_resource_busy = Bool()
  val alloc_resource_busy_cycle_count = UInt(32.W)
}

class cta_scheduler_top(val NUM_CU: Int = CONFIG.GPU.NUM_CU) extends Module {
  val io = IO(new Bundle{
    val host_wg_new = Flipped(DecoupledIO(new io_host2cta))     // From Host, New wg info
    val host_wg_done = DecoupledIO(new io_cta2host)             // To host, ID of wg which finished its execution

    // From CU(i), tag of wf which finished its execution
    val cu_wf_done = Vec(NUM_CU, Flipped(DecoupledIO(new io_cu2cuinterface)))
    // To CU(i), new wf info
    val cu_wf_new = Vec(NUM_CU, DecoupledIO(new io_cuinterface2cu))

    val celviz_debug = Output(new io_cta_scheduler_celviz_debug(NUM_CU))
  })
  dontTouch(io.celviz_debug)

  val wg_buffer_inst = Module(new wg_buffer)
  val allocator_inst = Module(new allocator)
  val resource_table_inst = Module(new resource_table_top)
  val cu_interface_inst = Module(new cu_interface)

  val init_ok = cu_interface_inst.io.init_ok
  wg_buffer_inst.io.host_wg_new.valid := io.host_wg_new.valid && init_ok
  io.host_wg_new.ready := wg_buffer_inst.io.host_wg_new.ready && init_ok
  io.host_wg_new.bits <> wg_buffer_inst.io.host_wg_new.bits

  wg_buffer_inst.io.alloc_wg_new <> allocator_inst.io.wgbuffer_wg_new
  allocator_inst.io.wgbuffer_result <> wg_buffer_inst.io.alloc_result
  wg_buffer_inst.io.cuinterface_wg_new <> cu_interface_inst.io.wgbuffer_wg_new
  allocator_inst.io.cuinterface_wg_new <> cu_interface_inst.io.alloc_wg_new
  cu_interface_inst.io.host_wg_done <> io.host_wg_done

  allocator_inst.io.rt_alloc <> resource_table_inst.io.alloc
  allocator_inst.io.rt_result_lds <> resource_table_inst.io.rtcache_lds
  allocator_inst.io.rt_result_sgpr <> resource_table_inst.io.rtcache_sgpr
  allocator_inst.io.rt_result_vgpr <> resource_table_inst.io.rtcache_vgpr
  resource_table_inst.io.dealloc <> cu_interface_inst.io.rt_dealloc
  resource_table_inst.io.cuinterface_wg_new <> cu_interface_inst.io.rt_wg_new
  allocator_inst.io.rt_dealloc <> resource_table_inst.io.slot_dealloc

  for(i <- 0 until NUM_CU) {
    io.cu_wf_new(i) <> cu_interface_inst.io.cu_wf_new(i)
    io.cu_wf_done(i) <> cu_interface_inst.io.cu_wf_done(i)
  }

  def eventCounter(event: Bool): UInt = {
    val count = RegInit(0.U(32.W))
    when(event) {
      count := count + 1.U
    }
    count
  }

  def eventCounterBy(increment: UInt): UInt = {
    val count = RegInit(0.U(32.W))
    when(increment =/= 0.U) {
      count := count + increment
    }
    count
  }

  val host_wg_accepted_fire = io.host_wg_new.fire
  val host_wg_stalled = io.host_wg_new.valid && !io.host_wg_new.ready
  val host_wg_done_fire = io.host_wg_done.fire
  val host_wg_done_stalled = io.host_wg_done.valid && !io.host_wg_done.ready
  val wgbuffer_alloc_dispatch_fire = wg_buffer_inst.io.alloc_wg_new.fire
  val wgbuffer_alloc_stalled = wg_buffer_inst.io.alloc_wg_new.valid && !wg_buffer_inst.io.alloc_wg_new.ready
  val alloc_result_accepted_fire = allocator_inst.io.wgbuffer_result.fire && allocator_inst.io.wgbuffer_result.bits.accept
  val alloc_result_rejected_fire = allocator_inst.io.wgbuffer_result.fire && !allocator_inst.io.wgbuffer_result.bits.accept
  val cuinterface_wg_enqueued_fire = cu_interface_inst.io.wgbuffer_wg_new.fire
  val cuinterface_wg_enqueue_stalled =
    (cu_interface_inst.io.wgbuffer_wg_new.valid ||
      cu_interface_inst.io.alloc_wg_new.valid ||
      cu_interface_inst.io.rt_wg_new.valid) &&
    !(cu_interface_inst.io.wgbuffer_wg_new.fire &&
      cu_interface_inst.io.alloc_wg_new.fire &&
      cu_interface_inst.io.rt_wg_new.fire)
  val cu_wf_dispatch_fire = VecInit((0 until NUM_CU).map(i => io.cu_wf_new(i).fire))
  val cu_wf_dispatch_stalled = VecInit((0 until NUM_CU).map(i => io.cu_wf_new(i).valid && !io.cu_wf_new(i).ready))
  val cu_wf_done_fire = VecInit((0 until NUM_CU).map(i => io.cu_wf_done(i).fire))
  val cu_wf_done_stalled = VecInit((0 until NUM_CU).map(i => io.cu_wf_done(i).valid && !io.cu_wf_done(i).ready))
  val rt_alloc_blocked = allocator_inst.io.rt_alloc.valid && !allocator_inst.io.rt_alloc.ready
  val rt_dealloc_blocked = cu_interface_inst.io.rt_dealloc.valid && !cu_interface_inst.io.rt_dealloc.ready
  val rt_wg_result_blocked = resource_table_inst.io.cuinterface_wg_new.valid && !resource_table_inst.io.cuinterface_wg_new.ready
  val resource_blocked_mask = Cat(rt_wg_result_blocked, rt_dealloc_blocked, rt_alloc_blocked, wgbuffer_alloc_stalled)
  val alloc_resource_busy =
    wgbuffer_alloc_stalled ||
    rt_alloc_blocked ||
    rt_dealloc_blocked ||
    rt_wg_result_blocked

  io.celviz_debug.host_wg_accepted := host_wg_accepted_fire
  io.celviz_debug.host_wg_stalled := host_wg_stalled
  io.celviz_debug.host_wg_done := host_wg_done_fire
  io.celviz_debug.host_wg_done_stalled := host_wg_done_stalled
  io.celviz_debug.wgbuffer_alloc_dispatch := wgbuffer_alloc_dispatch_fire
  io.celviz_debug.wgbuffer_alloc_stalled := wgbuffer_alloc_stalled
  io.celviz_debug.alloc_result_accepted := alloc_result_accepted_fire
  io.celviz_debug.alloc_result_rejected := alloc_result_rejected_fire
  io.celviz_debug.cuinterface_wg_enqueued := cuinterface_wg_enqueued_fire
  io.celviz_debug.cuinterface_wg_enqueue_stalled := cuinterface_wg_enqueue_stalled
  io.celviz_debug.cu_wf_dispatch_fire := cu_wf_dispatch_fire.asUInt
  io.celviz_debug.cu_wf_dispatch_stalled := cu_wf_dispatch_stalled.asUInt
  io.celviz_debug.cu_wf_done_fire := cu_wf_done_fire.asUInt
  io.celviz_debug.cu_wf_done_stalled := cu_wf_done_stalled.asUInt
  io.celviz_debug.rt_alloc_blocked := rt_alloc_blocked
  io.celviz_debug.rt_dealloc_blocked := rt_dealloc_blocked
  io.celviz_debug.rt_wg_result_blocked := rt_wg_result_blocked
  io.celviz_debug.resource_blocked_mask := resource_blocked_mask
  io.celviz_debug.host_wg_accepted_count := eventCounter(host_wg_accepted_fire)
  io.celviz_debug.host_wg_stalled_cycle_count := eventCounter(host_wg_stalled)
  io.celviz_debug.host_wg_done_count := eventCounter(host_wg_done_fire)
  io.celviz_debug.host_wg_done_stalled_cycle_count := eventCounter(host_wg_done_stalled)
  io.celviz_debug.wgbuffer_alloc_dispatch_count := eventCounter(wgbuffer_alloc_dispatch_fire)
  io.celviz_debug.wgbuffer_alloc_stalled_cycle_count := eventCounter(wgbuffer_alloc_stalled)
  io.celviz_debug.alloc_result_accepted_count := eventCounter(alloc_result_accepted_fire)
  io.celviz_debug.alloc_result_rejected_count := eventCounter(alloc_result_rejected_fire)
  io.celviz_debug.cuinterface_wg_enqueued_count := eventCounter(cuinterface_wg_enqueued_fire)
  io.celviz_debug.cuinterface_wg_enqueue_stalled_cycle_count := eventCounter(cuinterface_wg_enqueue_stalled)
  for(i <- 0 until NUM_CU) {
    io.celviz_debug.cu_wf_dispatch_fire_count(i) := eventCounter(cu_wf_dispatch_fire(i))
    io.celviz_debug.cu_wf_dispatch_stalled_cycle_count(i) := eventCounter(cu_wf_dispatch_stalled(i))
    io.celviz_debug.cu_wf_done_fire_count(i) := eventCounter(cu_wf_done_fire(i))
    io.celviz_debug.cu_wf_done_stalled_cycle_count(i) := eventCounter(cu_wf_done_stalled(i))
  }
  io.celviz_debug.cu_wf_dispatch_fire_total_count := eventCounterBy(PopCount(cu_wf_dispatch_fire))
  io.celviz_debug.cu_wf_dispatch_stalled_total_cycle_count := eventCounterBy(PopCount(cu_wf_dispatch_stalled))
  io.celviz_debug.cu_wf_done_fire_total_count := eventCounterBy(PopCount(cu_wf_done_fire))
  io.celviz_debug.cu_wf_done_stalled_total_cycle_count := eventCounterBy(PopCount(cu_wf_done_stalled))
  io.celviz_debug.alloc_resource_busy := alloc_resource_busy
  io.celviz_debug.alloc_resource_busy_cycle_count := eventCounter(alloc_resource_busy)
}

object emitVerilog extends App {
  chisel3.emitVerilog(
    new cta_scheduler_top(CONFIG.GPU.NUM_CU),
    Array("--target-dir", "generated/")
  )
}
