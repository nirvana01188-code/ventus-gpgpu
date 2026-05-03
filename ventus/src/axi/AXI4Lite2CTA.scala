/*
 * Copyright (c) 2021-2022 International Innovation Center of Tsinghua University, Shanghai
 * Ventus is licensed under Mulan PSL v2.
 * You can use this software according to the terms and conditions of the Mulan PSL v2.
 * You may obtain a copy of Mulan PSL v2 at:
 *          http://license.coscl.org.cn/MulanPSL2
 * THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
 * EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
 * MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
 * See the Mulan PSL v2 for more details. */

package axi

import chisel3._
import chisel3.util._
import top.parameters._
import top.host2CTA_data
import top.CTA2host_data

class AXI4Lite2CTA(val addrWidth:Int, val busWidth:Int) extends Module{
  val io = IO(new Bundle{
    val ctl = Flipped(new AXI4Lite(addrWidth, busWidth))
    //val bus = new CSRBusBundle(addrWidth, busWidth)
    val data = DecoupledIO(new host2CTA_data)
    val rsp = Flipped(Decoupled(new CTA2host_data))
  })

  val legacyLaunchReg = 0
  val legacyDoneWgIdReg = 16
  val legacyDoneValidReg = 17
  val legacyRegCount = 20
  val commandDoorbellReg = 20
  val commandCountReg = 21
  val commandIdReg = 22
  val kernelIdReg = 23
  val fenceIdReg = 24
  val irqStatusReg = 25
  val irqMaskReg = 26
  val irqClearReg = 27
  val irqPendingReg = 28
  val errorStatusReg = 29
  val apbAxilReadCountReg = 30
  val apbAxilWriteCountReg = 31
  val completionCountReg = 32
  val completionStatusReg = 33
  val completionCommandIdReg = 34
  val completionFenceIdReg = 35
  val completionWgIdReg = 36
  // Celviz acceptance-visible CSRs beyond the legacy CTA launch window.
  val queueDoorbellReg = commandDoorbellReg
  val queueDoorbellCountReg = 37
  val irqCountReg = 38
  val errorCountReg = 39
  val queueHeadReg = 40
  val queueTailReg = 41
  val queuePendingReg = 42
  val queueStatusReg = 43
  val schedulerHandoffCountReg = 44
  val schedulerBusyCycleCountReg = 45
  val apbReadCountReg = apbAxilReadCountReg
  val apbWriteCountReg = apbAxilWriteCountReg
  val axilReadCountReg = apbAxilReadCountReg
  val axilWriteCountReg = apbAxilWriteCountReg
  val regCount = 46
  val regAddrWidth = log2Ceil(regCount)

  val irqCommand = 1.U(busWidth.W)
  val irqCompletion = 2.U(busWidth.W)
  val irqError = 4.U(busWidth.W)
  val irqKnownMask = irqCommand | irqCompletion | irqError

  val errDoorbellBusy = 1.U(busWidth.W)
  val errRspBackpressure = 2.U(busWidth.W)
  val errInvalidRegAddr = 4.U(busWidth.W)
  val errReadOnlyWrite = 8.U(busWidth.W)
  val errKnownMask = errDoorbellBusy | errRspBackpressure | errInvalidRegAddr | errReadOnlyWrite

  val doorbellPending = 1.U(busWidth.W)
  val commandAccepted = 2.U(busWidth.W)
  val proxyDoorbell = 4.U(busWidth.W)
  val legacyDoorbell = 8.U(busWidth.W)
  val doorbellStatusMask = doorbellPending | commandAccepted | proxyDoorbell | legacyDoorbell
  val doorbellW1cMask = commandAccepted | proxyDoorbell | legacyDoorbell

  val completionPending = 1.U(busWidth.W)
  val completionSeen = 2.U(busWidth.W)
  val completionBackpressure = 4.U(busWidth.W)
  val completionStatusMask = completionPending | completionSeen | completionBackpressure

  val queueStatusEmpty = 1.U(busWidth.W)
  val queueStatusPending = 2.U(busWidth.W)
  val queueStatusSchedulerBusy = 4.U(busWidth.W)
  val queueStatusDoorbellBusy = 8.U(busWidth.W)
  val queueStatusIrqPending = 16.U(busWidth.W)
  val queueStatusError = 32.U(busWidth.W)

  val regs = RegInit(VecInit.fill(regCount)(0.U(busWidth.W)))
  val irqPendingBits = WireInit(regs(irqStatusReg) & regs(irqMaskReg) & irqKnownMask)
  val celvizCommandBusy = WireInit(regs(legacyLaunchReg)(0) || regs(commandDoorbellReg)(0))
  val celvizIrqPending = WireInit(irqPendingBits.orR)
  val celvizAxiMmioCounter = WireInit(regs(apbAxilReadCountReg) | regs(apbAxilWriteCountReg))
  val celvizQueueDoorbellStatus = WireInit(regs(queueDoorbellReg) & doorbellStatusMask)
  val celvizQueueDoorbellCounter = WireInit(regs(queueDoorbellCountReg))
  val celvizQueueHead = WireInit(regs(queueHeadReg))
  val celvizQueueTail = WireInit(regs(queueTailReg))
  val celvizQueuePending = WireInit(regs(queuePendingReg))
  val celvizQueueStatus = WireInit(regs(queueStatusReg))
  val celvizQueueNonEmpty = WireInit(regs(queuePendingReg) =/= 0.U)
  val celvizCommandCounter = WireInit(regs(commandCountReg))
  val celvizCompletionCounter = WireInit(regs(completionCountReg))
  val celvizIrqCounter = WireInit(regs(irqCountReg))
  val celvizErrorCounter = WireInit(regs(errorCountReg))
  val celvizSchedulerHandoffCounter = WireInit(regs(schedulerHandoffCountReg))
  val celvizSchedulerBusyCycleCounter = WireInit(regs(schedulerBusyCycleCountReg))
  val celvizApbReadCounter = WireInit(regs(apbReadCountReg))
  val celvizApbWriteCounter = WireInit(regs(apbWriteCountReg))
  val celvizAxiReadCounter = WireInit(regs(axilReadCountReg))
  val celvizAxiWriteCounter = WireInit(regs(axilWriteCountReg))
  val celvizCompletionPulse = WireDefault(false.B)
  val celvizCommandAcceptedPulse = WireDefault(false.B)
  val celvizQueueEnqueuePulse = WireDefault(false.B)
  val celvizSchedulerHandoffPulse = WireDefault(false.B)
  val celvizQueueDoorbellAcceptedPulse = WireDefault(false.B)
  val celvizAxiReadFire = WireDefault(false.B)
  val celvizAxiWriteFire = WireDefault(false.B)
  val celvizErrorRspBackpressurePulse = WireDefault(false.B)
  val celvizErrorReadInvalidPulse = WireDefault(false.B)
  val celvizErrorWriteReadOnlyPulse = WireDefault(false.B)
  val celvizErrorWriteInvalidPulse = WireDefault(false.B)
  val celvizErrorDoorbellBusyPulse = WireDefault(false.B)
  dontTouch(celvizCommandBusy)
  dontTouch(celvizIrqPending)
  dontTouch(celvizAxiMmioCounter)
  dontTouch(celvizQueueDoorbellStatus)
  dontTouch(celvizQueueDoorbellCounter)
  dontTouch(celvizQueueHead)
  dontTouch(celvizQueueTail)
  dontTouch(celvizQueuePending)
  dontTouch(celvizQueueStatus)
  dontTouch(celvizQueueNonEmpty)
  dontTouch(celvizCommandCounter)
  dontTouch(celvizCompletionCounter)
  dontTouch(celvizIrqCounter)
  dontTouch(celvizErrorCounter)
  dontTouch(celvizSchedulerHandoffCounter)
  dontTouch(celvizSchedulerBusyCycleCounter)
  dontTouch(celvizApbReadCounter)
  dontTouch(celvizApbWriteCounter)
  dontTouch(celvizAxiReadCounter)
  dontTouch(celvizAxiWriteCounter)
  dontTouch(celvizCompletionPulse)
  dontTouch(celvizCommandAcceptedPulse)
  dontTouch(celvizQueueEnqueuePulse)
  dontTouch(celvizSchedulerHandoffPulse)
  dontTouch(celvizQueueDoorbellAcceptedPulse)
  dontTouch(celvizAxiReadFire)
  dontTouch(celvizAxiWriteFire)
  dontTouch(celvizErrorRspBackpressurePulse)
  dontTouch(celvizErrorReadInvalidPulse)
  dontTouch(celvizErrorWriteReadOnlyPulse)
  dontTouch(celvizErrorWriteInvalidPulse)
  dontTouch(celvizErrorDoorbellBusyPulse)

  io.rsp.ready:=false.B
  when(io.rsp.valid& !regs(legacyDoneValidReg)(0)){
    io.rsp.ready:=true.B
    regs(legacyDoneValidReg):=1.U
    regs(legacyDoneWgIdReg):=io.rsp.bits.inflight_wg_buffer_host_wf_done_wg_id
    regs(completionCountReg) := regs(completionCountReg) + 1.U
    regs(completionStatusReg) := regs(completionStatusReg) | completionPending | completionSeen
    regs(completionCommandIdReg) := regs(commandIdReg)
    regs(completionFenceIdReg) := regs(fenceIdReg)
    regs(completionWgIdReg) := io.rsp.bits.inflight_wg_buffer_host_wf_done_wg_id
    regs(irqStatusReg) := regs(irqStatusReg) | irqCompletion
    celvizCompletionPulse := true.B
  }.elsewhen(io.rsp.valid & regs(legacyDoneValidReg)(0)){
    regs(errorStatusReg) := regs(errorStatusReg) | errRspBackpressure
    regs(completionStatusReg) := regs(completionStatusReg) | completionBackpressure
    regs(irqStatusReg) := regs(irqStatusReg) | irqError
    celvizErrorRspBackpressurePulse := true.B
  }

  val sIdle :: sReadAddr :: sReadData :: sWriteAddr :: sWriteData :: sWriteResp :: Nil = Enum(6)
  val state = RegInit(sIdle)

  val awready = RegInit(false.B)
  val wready = RegInit(false.B)
  val bvalid = RegInit(false.B)
  val bresp = WireInit(0.U(AXI4Lite.respWidth.W))

  val arready = RegInit(false.B)
  val rvalid = RegInit(false.B)
  val rresp = WireInit(0.U(AXI4Lite.respWidth.W))

  val addr = RegInit(0.U(addrWidth.W))
  val regIndex = addr(regAddrWidth - 1, 0)
  val addrInRange = addr < regCount.U

  val read = RegInit(false.B)
  val write = RegInit(false.B)
  val dataOut = RegInit(0.U(busWidth.W))

  val transaction_id = RegInit(0.U(AXI4Lite.idWidth.W))

  val rdata = WireInit(0.U(busWidth.W))
  val rdata_reg = RegInit(0.U(busWidth.W))
  val regReadData = WireInit(0.U(busWidth.W))
  when(addrInRange) {
    regReadData := regs(regIndex)
  }
  when(addr === irqClearReg.U(addrWidth.W)) {
    regReadData := 0.U
  }
  when(addr === irqPendingReg.U(addrWidth.W)) {
    regReadData := irqPendingBits
  }
  rdata_reg := rdata
  rdata := rdata_reg
  when(RegNext(io.ctl.r.rready) || !RegNext(rvalid)){
    rdata := regReadData
  }
  //  rdata := RegNext(rdata)
  io.ctl.r.rdata := rdata
  //  io.ctl.r.rdata := regs(addr)
  io.ctl.r.rid := transaction_id


  io.ctl.aw.awready := awready
  io.ctl.w.wready := wready
  io.ctl.b.bvalid := bvalid
  io.ctl.b.bresp := bresp
  io.ctl.b.bid := transaction_id

  io.ctl.ar.arready := arready
  io.ctl.r.rvalid := rvalid
  io.ctl.r.rresp := rresp


  val out_sIdle::out_sOutput::Nil=Enum(2)
  val out_state=RegInit(out_sIdle)
  val input_valid=regs(legacyLaunchReg)(0)
  val celvizQueueSchedulerBusy = WireInit(out_state =/= out_sIdle)
  val celvizQueueLifecycleIdle = WireInit(regs(queuePendingReg) === 0.U && out_state === out_sIdle && !input_valid)
  val celvizQueueLifecyclePending = WireInit(regs(queuePendingReg) =/= 0.U || input_valid)
  val queueStatusNext = WireInit(0.U(busWidth.W))
  queueStatusNext := Mux(celvizQueueLifecycleIdle, queueStatusEmpty, 0.U) |
    Mux(celvizQueueLifecyclePending, queueStatusPending, 0.U) |
    Mux(celvizQueueSchedulerBusy, queueStatusSchedulerBusy, 0.U) |
    Mux(celvizCommandBusy, queueStatusDoorbellBusy, 0.U) |
    Mux(celvizIrqPending, queueStatusIrqPending, 0.U) |
    Mux((regs(errorStatusReg) & errKnownMask).orR, queueStatusError, 0.U)
  dontTouch(celvizQueueSchedulerBusy)
  dontTouch(celvizQueueLifecycleIdle)
  dontTouch(celvizQueueLifecyclePending)
  dontTouch(queueStatusNext)
  io.data.valid:=input_valid & out_state===out_sOutput // TODO: New AXI
  io.data.bits.host_wg_id:=regs(1)
  io.data.bits.host_num_wf:=regs(2)
  io.data.bits.host_wf_size:=regs(3)
  io.data.bits.host_start_pc:=regs(4)
  io.data.bits.host_vgpr_size_total:=regs(5)
  io.data.bits.host_sgpr_size_total:=regs(6)
  io.data.bits.host_lds_size_total:=regs(7)
  io.data.bits.host_gds_size_total:=0.U
  io.data.bits.host_vgpr_size_per_wf:=regs(8)
  io.data.bits.host_sgpr_size_per_wf:=regs(9)
  io.data.bits.host_gds_baseaddr:=regs(10)
  io.data.bits.host_pds_baseaddr:=regs(11)
  io.data.bits.host_csr_knl:=regs(12)
  io.data.bits.host_kernel_size_3d(0):=regs(13)
  io.data.bits.host_kernel_size_3d(1):=regs(14)
  io.data.bits.host_kernel_size_3d(2):=regs(15)
  io.data.bits.host_pds_size_per_wf := regs(18)
  io.data.bits.host_asid := regs(19)
  io.data.bits.host_kernel_asid := regs(19)

  switch(out_state) {
    is(out_sIdle) {
      when(input_valid) {
        out_state := out_sOutput
      }
    }
    is(out_sOutput) {
      when(io.data.fire) {
        out_state := out_sIdle
        regs(legacyLaunchReg):=0.U
        regs(commandDoorbellReg) := (regs(commandDoorbellReg) & ~doorbellPending) | commandAccepted
        celvizSchedulerHandoffPulse := true.B
      }
    }
  }
  when(write) {
    regs(apbAxilWriteCountReg) := regs(apbAxilWriteCountReg) + 1.U
    when(addr < legacyRegCount.U) {
      regs(regIndex) := dataOut
    }.elsewhen(addr === commandIdReg.U(addrWidth.W) ||
      addr === kernelIdReg.U(addrWidth.W) ||
      addr === fenceIdReg.U(addrWidth.W)) {
      regs(regIndex) := dataOut
    }.elsewhen(addr === irqMaskReg.U(addrWidth.W)) {
      regs(irqMaskReg) := dataOut & irqKnownMask
    }.elsewhen(addr === irqStatusReg.U(addrWidth.W)) {
      regs(irqStatusReg) := regs(irqStatusReg) & ~(dataOut & irqKnownMask)
    }.elsewhen(addr === irqClearReg.U(addrWidth.W)) {
      regs(irqStatusReg) := regs(irqStatusReg) & ~(dataOut & irqKnownMask)
    }.elsewhen(addr === errorStatusReg.U(addrWidth.W)) {
      regs(errorStatusReg) := regs(errorStatusReg) & ~(dataOut & errKnownMask)
    }.elsewhen(addr === completionStatusReg.U(addrWidth.W)) {
      regs(completionStatusReg) := regs(completionStatusReg) & ~(dataOut & completionStatusMask)
      when(dataOut(0)) {
        regs(legacyDoneValidReg) := 0.U
      }
    }.elsewhen(addr === commandDoorbellReg.U(addrWidth.W)) {
      regs(commandDoorbellReg) := regs(commandDoorbellReg) & ~(dataOut & doorbellW1cMask)
    }.elsewhen(addrInRange) {
      regs(errorStatusReg) := regs(errorStatusReg) | errReadOnlyWrite
      regs(irqStatusReg) := regs(irqStatusReg) | irqError
      celvizErrorWriteReadOnlyPulse := true.B
    }.otherwise {
      regs(errorStatusReg) := regs(errorStatusReg) | errInvalidRegAddr
      regs(irqStatusReg) := regs(irqStatusReg) | irqError
      celvizErrorWriteInvalidPulse := true.B
    }

    when((addr === legacyLaunchReg.U(addrWidth.W) && dataOut(0)) ||
      (addr === commandDoorbellReg.U(addrWidth.W) && dataOut(0))) {
      when(celvizCommandBusy) {
        regs(errorStatusReg) := regs(errorStatusReg) | errDoorbellBusy
        regs(irqStatusReg) := regs(irqStatusReg) | irqError
        celvizErrorDoorbellBusyPulse := true.B
      }.otherwise {
        regs(commandCountReg) := regs(commandCountReg) + 1.U
        regs(irqStatusReg) := regs(irqStatusReg) | irqCommand
        celvizCommandAcceptedPulse := true.B
        celvizQueueEnqueuePulse := true.B
        when(addr === commandDoorbellReg.U(addrWidth.W)) {
          regs(legacyLaunchReg) := regs(legacyLaunchReg) | 1.U
          regs(commandDoorbellReg) := doorbellPending | proxyDoorbell
          celvizQueueDoorbellAcceptedPulse := true.B
        }.otherwise {
          regs(commandDoorbellReg) := doorbellPending | legacyDoorbell
        }
      }
    }

    when(addr === legacyDoneValidReg.U(addrWidth.W) && !dataOut(0)) {
      regs(completionStatusReg) := regs(completionStatusReg) & ~completionPending
    }
  }
  val celvizErrorEventCount = celvizErrorRspBackpressurePulse.asUInt + celvizErrorReadInvalidPulse.asUInt +
    celvizErrorWriteReadOnlyPulse.asUInt + celvizErrorWriteInvalidPulse.asUInt + celvizErrorDoorbellBusyPulse.asUInt
  val celvizIrqEventCount = celvizCommandAcceptedPulse.asUInt + celvizCompletionPulse.asUInt + celvizErrorEventCount
  when(celvizQueueDoorbellAcceptedPulse) {
    regs(queueDoorbellCountReg) := regs(queueDoorbellCountReg) + 1.U
  }
  when(celvizQueueEnqueuePulse) {
    regs(queueTailReg) := regs(queueTailReg) + 1.U
  }
  when(celvizSchedulerHandoffPulse) {
    regs(queueHeadReg) := regs(queueHeadReg) + 1.U
    regs(schedulerHandoffCountReg) := regs(schedulerHandoffCountReg) + 1.U
  }
  when(celvizQueueEnqueuePulse && !celvizSchedulerHandoffPulse) {
    regs(queuePendingReg) := regs(queuePendingReg) + 1.U
  }.elsewhen(!celvizQueueEnqueuePulse && celvizSchedulerHandoffPulse && regs(queuePendingReg) =/= 0.U) {
    regs(queuePendingReg) := regs(queuePendingReg) - 1.U
  }
  when(celvizQueueSchedulerBusy) {
    regs(schedulerBusyCycleCountReg) := regs(schedulerBusyCycleCountReg) + 1.U
  }
  when(celvizErrorEventCount =/= 0.U) {
    regs(errorCountReg) := regs(errorCountReg) + celvizErrorEventCount
  }
  when(celvizIrqEventCount =/= 0.U) {
    regs(irqCountReg) := regs(irqCountReg) + celvizIrqEventCount
  }
  regs(irqPendingReg) := irqPendingBits
  regs(irqClearReg) := 0.U
  regs(queueStatusReg) := queueStatusNext

  switch(state){
    is(sIdle){
      rvalid := false.B
      bvalid := false.B
      read := false.B
      write := false.B
      transaction_id := 0.U
      when(io.ctl.aw.awvalid&out_state===out_sIdle){
        state := sWriteAddr
        transaction_id := io.ctl.aw.awid
      }.elsewhen(io.ctl.ar.arvalid){
        state := sReadAddr
        transaction_id := io.ctl.ar.arid
      }

    }
    is(sReadAddr){
      arready := true.B
      when(io.ctl.ar.arvalid && arready){
        state := sReadData
        addr := io.ctl.ar.araddr(addrWidth - 1, 2)
        read := true.B
        regs(apbAxilReadCountReg) := regs(apbAxilReadCountReg) + 1.U
        celvizAxiReadFire := true.B
        when(io.ctl.ar.araddr(addrWidth - 1, 2) >= regCount.U) {
          regs(errorStatusReg) := regs(errorStatusReg) | errInvalidRegAddr
          regs(irqStatusReg) := regs(irqStatusReg) | irqError
          celvizErrorReadInvalidPulse := true.B
        }
        arready := false.B
      }
    }
    is(sReadData){
      rvalid := true.B
      when(io.ctl.r.rready && rvalid){
        state := sIdle
        rvalid := false.B
      }
    }
    is(sWriteAddr){
      awready := true.B
      when(io.ctl.aw.awvalid && awready){
        addr := io.ctl.aw.awaddr(addrWidth - 1, 2)
        state := sWriteData
        awready := false.B
      }
    }
    is(sWriteData){
      wready := true.B
      when(io.ctl.w.wvalid && wready){
        state := sWriteResp
        dataOut := io.ctl.w.wdata
        write := true.B
        celvizAxiWriteFire := true.B
        wready := false.B
      }
    }
    is(sWriteResp){
      write := false.B
      wready := false.B
      bvalid := true.B
      when(io.ctl.b.bready && bvalid){
        state := sIdle
        bvalid := false.B
      }
    }
  }

}


trait HasPipelineReg{ this: CTA_IO =>
  def latency: Int

  //val ready = Wire(Bool())
  //val cnt = RegInit(0.U((log2Up(latency)+1).W))

  //ready := (cnt < latency.U) || (cnt === latency.U && io.out.ready)
  //cnt := cnt + io.in.fire - io.out.fire

  val valids = io.in.valid +: Array.fill(latency)(RegInit(false.B))
  for(i <- 1 to latency){
    when(!(!io.out.ready && valids.drop(i).reduce(_&&_) )){ valids(i) := valids(i-1) }
  }

  def PipelineReg[T<:Data](i: Int)(next: T) = RegEnable(next,valids(i-1) && !(!io.out.ready && valids.drop(i).reduce(_&&_) ))
  def S1Reg[T<:Data](next: T):T = PipelineReg[T](1)(next)
  def S2Reg[T<:Data](next: T):T = PipelineReg[T](2)(next)
  def S3Reg[T<:Data](next: T):T = PipelineReg[T](3)(next)
  def S4Reg[T<:Data](next: T):T = PipelineReg[T](4)(next)
  def S5Reg[T<:Data](next: T):T = PipelineReg[T](5)(next)

  io.in.ready := !(!io.out.ready && valids.drop(1).reduce(_&&_))
  io.out.valid := valids.last
}


abstract class CTA_IO extends Module {
  val io=IO(new Bundle{
    val in = Flipped(DecoupledIO(new host2CTA_data))
    val out = (Decoupled(new CTA2host_data))
  })
}

class CTA_module extends CTA_IO with HasPipelineReg{
  def latency = 5
  io.out.bits.inflight_wg_buffer_host_wf_done_wg_id:=S5Reg(S4Reg(S3Reg(S2Reg(S1Reg(io.in.bits.host_wg_id)))))
}


class AXIwrapper_test(val addrWidth:Int, val busWidth:Int) extends Module{
  val io=IO(new Bundle{
    val ctl = Flipped(new AXI4Lite(addrWidth, busWidth))
  })
  val axiAdapter=Module(new AXI4Lite2CTA(addrWidth,busWidth))
  val cta_module=Module(new CTA_module)
  axiAdapter.io.ctl<>io.ctl
  axiAdapter.io.data<>cta_module.io.in
  axiAdapter.io.rsp<>cta_module.io.out
}
