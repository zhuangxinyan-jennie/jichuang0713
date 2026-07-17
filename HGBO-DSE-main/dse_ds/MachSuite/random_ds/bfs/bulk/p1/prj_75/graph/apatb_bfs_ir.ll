; ModuleID = '/home/noel/Documents/HGBO-DSE-main/benchmark/MachSuite/bfs/bulk/bfs_random_prj_p1/solution/.autopilot/db/a.g.ld.5.gdce.bc'
source_filename = "llvm-link"
target datalayout = "e-m:e-i64:64-i128:128-i256:256-i512:512-i1024:1024-i2048:2048-i4096:4096-n8:16:32:64-S128-v16:16-v24:32-v32:32-v48:64-v96:128-v192:256-v256:256-v512:512-v1024:1024"
target triple = "fpga64-xilinx-none"

%struct.node_t_struct = type { i64, i64 }
%struct.edge_t_struct = type { i64 }

; Function Attrs: inaccessiblememonly nounwind
declare void @llvm.sideeffect() #0

; Function Attrs: noinline
define void @apatb_bfs_ir(%struct.node_t_struct* noalias nocapture nonnull readonly "fpga.decayed.dim.hint"="256" %nodes, %struct.edge_t_struct* noalias nocapture nonnull readonly "fpga.decayed.dim.hint"="4096" %edges, i64 %starting_node, i8* noalias nocapture nonnull "fpga.decayed.dim.hint"="256" %level, i64* noalias nocapture nonnull "fpga.decayed.dim.hint"="10" %level_counts) local_unnamed_addr #1 {
entry:
  %malloccall = call i8* @malloc(i64 4096)
  %nodes_copy2 = bitcast i8* %malloccall to [128 x i256]*
  %malloccall1 = call i8* @malloc(i64 32768)
  %edges_copy3 = bitcast i8* %malloccall1 to [2048 x i128]*
  %level_copy_0 = alloca [128 x i8], align 512
  %level_copy_1 = alloca [128 x i8], align 512
  %level_counts_copy4 = alloca [5 x i128], align 512
  %0 = bitcast %struct.node_t_struct* %nodes to [256 x %struct.node_t_struct]*
  %1 = bitcast %struct.edge_t_struct* %edges to [4096 x %struct.edge_t_struct]*
  %2 = bitcast i8* %level to [256 x i8]*
  %3 = bitcast i64* %level_counts to [10 x i64]*
  call void @copy_in([256 x %struct.node_t_struct]* nonnull %0, [128 x i256]* %nodes_copy2, [4096 x %struct.edge_t_struct]* nonnull %1, [2048 x i128]* %edges_copy3, [256 x i8]* nonnull %2, [128 x i8]* nonnull align 512 %level_copy_0, [128 x i8]* nonnull align 512 %level_copy_1, [10 x i64]* nonnull %3, [5 x i128]* nonnull align 512 %level_counts_copy4)
  %4 = getelementptr [128 x i256], [128 x i256]* %nodes_copy2, i32 0, i32 0
  %5 = getelementptr [2048 x i128], [2048 x i128]* %edges_copy3, i32 0, i32 0
  %level_copy.gep_0 = getelementptr [128 x i8], [128 x i8]* %level_copy_0, i64 0, i32 0
  %level_copy.gep_1 = getelementptr [128 x i8], [128 x i8]* %level_copy_1, i64 0, i32 0
  %level_counts_copy.gep5 = getelementptr [5 x i128], [5 x i128]* %level_counts_copy4, i64 0, i32 0
  call void @llvm.sideeffect() #0 [ "xlx_array_reshape"(i256* %4, i32 0, i32 1, i32 0) ], !dbg !5
  call void @llvm.sideeffect() #0 [ "xlx_array_reshape"(i128* %5, i32 0, i32 1, i32 0) ], !dbg !40
  call void @llvm.sideeffect() #0 [ "xlx_array_partition"(i8* %level_copy.gep_0, i32 0, i32 1, i32 0, i1 false) ], !dbg !41
  call void @llvm.sideeffect() #0 [ "xlx_array_partition"(i8* %level_copy.gep_1, i32 0, i32 1, i32 0, i1 false) ], !dbg !41
  call void @llvm.sideeffect() #0 [ "xlx_array_reshape"(i128* %level_counts_copy.gep5, i32 0, i32 1, i32 0) ], !dbg !42
  call void @apatb_bfs_hw([128 x i256]* %nodes_copy2, [2048 x i128]* %edges_copy3, i64 %starting_node, [128 x i8]* %level_copy_0, [128 x i8]* %level_copy_1, [5 x i128]* %level_counts_copy4)
  call void @copy_back([256 x %struct.node_t_struct]* %0, [128 x i256]* %nodes_copy2, [4096 x %struct.edge_t_struct]* %1, [2048 x i128]* %edges_copy3, [256 x i8]* %2, [128 x i8]* %level_copy_0, [128 x i8]* %level_copy_1, [10 x i64]* %3, [5 x i128]* %level_counts_copy4)
  call void @free(i8* %malloccall)
  call void @free(i8* %malloccall1)
  ret void
}

declare noalias i8* @malloc(i64) local_unnamed_addr

declare void @free(i8*) local_unnamed_addr

; Function Attrs: nounwind
declare void @llvm.assume(i1) #2

; Function Attrs: argmemonly noinline norecurse
define internal void @onebyonecpy_hls.p0a256i8.3.4([128 x i8]* noalias align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="0" %_0, [128 x i8]* noalias align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="0" %_1, [256 x i8]* noalias readonly "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1") #3 {
entry:
  %1 = icmp eq [128 x i8]* %_0, null
  %2 = icmp eq [256 x i8]* %0, null
  %3 = or i1 %1, %2
  br i1 %3, label %ret, label %copy

copy:                                             ; preds = %entry
  br label %for.loop

for.loop:                                         ; preds = %dst.addr.exit, %copy
  %for.loop.idx1 = phi i64 [ 0, %copy ], [ %for.loop.idx.next, %dst.addr.exit ]
  %4 = urem i64 %for.loop.idx1, 2
  %5 = udiv i64 %for.loop.idx1, 2
  %dst.addr_0 = getelementptr [128 x i8], [128 x i8]* %_0, i64 0, i64 %5
  %dst.addr_1 = getelementptr [128 x i8], [128 x i8]* %_1, i64 0, i64 %5
  %src.addr = getelementptr [256 x i8], [256 x i8]* %0, i64 0, i64 %for.loop.idx1
  %6 = load i8, i8* %src.addr, align 1
  %7 = trunc i64 %4 to i1
  %cond = icmp eq i1 %7, false
  br i1 %cond, label %dst.addr.case.0, label %dst.addr.case.1

dst.addr.case.0:                                  ; preds = %for.loop
  store i8 %6, i8* %dst.addr_0, align 1
  br label %dst.addr.exit

dst.addr.case.1:                                  ; preds = %for.loop
  call void @llvm.assume(i1 %7)
  store i8 %6, i8* %dst.addr_1, align 1
  br label %dst.addr.exit

dst.addr.exit:                                    ; preds = %dst.addr.case.1, %dst.addr.case.0
  %for.loop.idx.next = add nuw nsw i64 %for.loop.idx1, 1
  %exitcond = icmp ne i64 %for.loop.idx.next, 256
  br i1 %exitcond, label %for.loop, label %ret

ret:                                              ; preds = %dst.addr.exit, %entry
  ret void
}

; Function Attrs: argmemonly noinline norecurse
define internal void @onebyonecpy_hls.p0a256i8.9.10([256 x i8]* noalias "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="0", [128 x i8]* noalias readonly align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1" %_0, [128 x i8]* noalias readonly align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1" %_1) #3 {
entry:
  %1 = icmp eq [256 x i8]* %0, null
  %2 = icmp eq [128 x i8]* %_0, null
  %3 = or i1 %1, %2
  br i1 %3, label %ret, label %copy

copy:                                             ; preds = %entry
  br label %for.loop

for.loop:                                         ; preds = %src.addr.exit, %copy
  %for.loop.idx1 = phi i64 [ 0, %copy ], [ %for.loop.idx.next, %src.addr.exit ]
  %dst.addr = getelementptr [256 x i8], [256 x i8]* %0, i64 0, i64 %for.loop.idx1
  %4 = urem i64 %for.loop.idx1, 2
  %5 = udiv i64 %for.loop.idx1, 2
  %src.addr_0 = getelementptr [128 x i8], [128 x i8]* %_0, i64 0, i64 %5
  %src.addr_1 = getelementptr [128 x i8], [128 x i8]* %_1, i64 0, i64 %5
  %6 = trunc i64 %4 to i1
  %cond = icmp eq i1 %6, false
  br i1 %cond, label %src.addr.case.0, label %src.addr.case.1

src.addr.case.0:                                  ; preds = %for.loop
  %_01 = load i8, i8* %src.addr_0, align 1
  br label %src.addr.exit

src.addr.case.1:                                  ; preds = %for.loop
  call void @llvm.assume(i1 %6)
  %_12 = load i8, i8* %src.addr_1, align 1
  br label %src.addr.exit

src.addr.exit:                                    ; preds = %src.addr.case.1, %src.addr.case.0
  %7 = phi i8 [ %_01, %src.addr.case.0 ], [ %_12, %src.addr.case.1 ]
  store i8 %7, i8* %dst.addr, align 1
  %for.loop.idx.next = add nuw nsw i64 %for.loop.idx1, 1
  %exitcond = icmp ne i64 %for.loop.idx.next, 256
  br i1 %exitcond, label %for.loop, label %ret

ret:                                              ; preds = %src.addr.exit, %entry
  ret void
}

; Function Attrs: argmemonly noinline norecurse
define internal void @onebyonecpy_hls.p0a256struct.node_t_struct([128 x i256]* noalias "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="0", [256 x %struct.node_t_struct]* noalias readonly "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1") #3 {
entry:
  %2 = icmp eq [128 x i256]* %0, null
  %3 = icmp eq [256 x %struct.node_t_struct]* %1, null
  %4 = or i1 %2, %3
  br i1 %4, label %ret, label %copy

copy:                                             ; preds = %entry
  br label %for.loop

for.loop:                                         ; preds = %for.loop, %copy
  %for.loop.idx5 = phi i64 [ 0, %copy ], [ %for.loop.idx.next, %for.loop ]
  %src.addr.01 = getelementptr [256 x %struct.node_t_struct], [256 x %struct.node_t_struct]* %1, i64 0, i64 %for.loop.idx5, i32 0
  %5 = udiv i64 %for.loop.idx5, 128
  %6 = mul i64 128, %5
  %7 = urem i64 %for.loop.idx5, 128
  %8 = getelementptr [128 x i256], [128 x i256]* %0, i64 0, i64 %7
  %9 = load i64, i64* %src.addr.01, align 8
  %10 = zext i64 %9 to i128
  %src.addr.13 = getelementptr [256 x %struct.node_t_struct], [256 x %struct.node_t_struct]* %1, i64 0, i64 %for.loop.idx5, i32 1
  %11 = load i64, i64* %src.addr.13, align 8
  %12 = zext i64 %11 to i128
  %13 = shl i128 %12, 64
  %.partset = or i128 %13, %10
  %14 = load i256, i256* %8, align 32
  %15 = zext i64 %6 to i256
  %16 = shl i256 340282366920938463463374607431768211455, %15
  %17 = zext i128 %.partset to i256
  %18 = shl i256 %17, %15
  %19 = xor i256 %16, -1
  %20 = and i256 %14, %19
  %21 = or i256 %20, %18
  store i256 %21, i256* %8, align 32
  %for.loop.idx.next = add nuw nsw i64 %for.loop.idx5, 1
  %exitcond = icmp ne i64 %for.loop.idx.next, 256
  br i1 %exitcond, label %for.loop, label %ret

ret:                                              ; preds = %for.loop, %entry
  ret void
}

; Function Attrs: argmemonly noinline norecurse
define internal void @onebyonecpy_hls.p0a4096struct.edge_t_struct.22([2048 x i128]* noalias "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="0", [4096 x %struct.edge_t_struct]* noalias readonly "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1") #3 {
entry:
  %2 = icmp eq [2048 x i128]* %0, null
  %3 = icmp eq [4096 x %struct.edge_t_struct]* %1, null
  %4 = or i1 %2, %3
  br i1 %4, label %ret, label %copy

copy:                                             ; preds = %entry
  br label %for.loop

for.loop:                                         ; preds = %for.loop, %copy
  %for.loop.idx3 = phi i64 [ 0, %copy ], [ %for.loop.idx.next, %for.loop ]
  %src.addr.01 = getelementptr [4096 x %struct.edge_t_struct], [4096 x %struct.edge_t_struct]* %1, i64 0, i64 %for.loop.idx3, i32 0
  %5 = urem i64 %for.loop.idx3, 2
  %6 = mul i64 64, %5
  %7 = udiv i64 %for.loop.idx3, 2
  %8 = getelementptr [2048 x i128], [2048 x i128]* %0, i64 0, i64 %7
  %9 = load i64, i64* %src.addr.01, align 8
  %10 = load i128, i128* %8, align 16
  %11 = zext i64 %6 to i128
  %12 = shl i128 18446744073709551615, %11
  %13 = zext i64 %9 to i128
  %14 = shl i128 %13, %11
  %15 = xor i128 %12, -1
  %16 = and i128 %10, %15
  %17 = or i128 %16, %14
  store i128 %17, i128* %8, align 16
  %for.loop.idx.next = add nuw nsw i64 %for.loop.idx3, 1
  %exitcond = icmp ne i64 %for.loop.idx.next, 4096
  br i1 %exitcond, label %for.loop, label %ret

ret:                                              ; preds = %for.loop, %entry
  ret void
}

; Function Attrs: argmemonly noinline norecurse
define internal void @onebyonecpy_hls.p0a10i64.31.32([5 x i128]* noalias align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="0", [10 x i64]* noalias readonly "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1") #3 {
entry:
  %2 = icmp eq [5 x i128]* %0, null
  %3 = icmp eq [10 x i64]* %1, null
  %4 = or i1 %2, %3
  br i1 %4, label %ret, label %copy

copy:                                             ; preds = %entry
  br label %for.loop

for.loop:                                         ; preds = %for.loop, %copy
  %for.loop.idx1 = phi i64 [ 0, %copy ], [ %for.loop.idx.next, %for.loop ]
  %5 = urem i64 %for.loop.idx1, 2
  %6 = mul i64 64, %5
  %7 = udiv i64 %for.loop.idx1, 2
  %dst.addr1 = getelementptr [5 x i128], [5 x i128]* %0, i64 0, i64 %7
  %src.addr = getelementptr [10 x i64], [10 x i64]* %1, i64 0, i64 %for.loop.idx1
  %8 = load i64, i64* %src.addr, align 8
  %9 = load i128, i128* %dst.addr1, align 16
  %10 = zext i64 %6 to i128
  %11 = shl i128 18446744073709551615, %10
  %12 = zext i64 %8 to i128
  %13 = shl i128 %12, %10
  %14 = xor i128 %11, -1
  %15 = and i128 %9, %14
  %16 = or i128 %15, %13
  store i128 %16, i128* %dst.addr1, align 16
  %for.loop.idx.next = add nuw nsw i64 %for.loop.idx1, 1
  %exitcond = icmp ne i64 %for.loop.idx.next, 10
  br i1 %exitcond, label %for.loop, label %ret

ret:                                              ; preds = %for.loop, %entry
  ret void
}

; Function Attrs: argmemonly noinline norecurse
define internal void @copy_in([256 x %struct.node_t_struct]* noalias readonly "orig.arg.no"="0", [128 x i256]* noalias "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1", [4096 x %struct.edge_t_struct]* noalias readonly "orig.arg.no"="2", [2048 x i128]* noalias "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="3", [256 x i8]* noalias readonly "orig.arg.no"="4", [128 x i8]* noalias align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="5" %_0, [128 x i8]* noalias align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="5" %_1, [10 x i64]* noalias readonly "orig.arg.no"="6", [5 x i128]* noalias align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="7") #4 {
entry:
  call void @onebyonecpy_hls.p0a256struct.node_t_struct([128 x i256]* %1, [256 x %struct.node_t_struct]* %0)
  call void @onebyonecpy_hls.p0a4096struct.edge_t_struct.22([2048 x i128]* %3, [4096 x %struct.edge_t_struct]* %2)
  call void @onebyonecpy_hls.p0a256i8.3.4([128 x i8]* align 512 %_0, [128 x i8]* align 512 %_1, [256 x i8]* %4)
  call void @onebyonecpy_hls.p0a10i64.31.32([5 x i128]* align 512 %6, [10 x i64]* %5)
  ret void
}

; Function Attrs: argmemonly noinline norecurse
define internal void @onebyonecpy_hls.p0a256struct.node_t_struct.15([256 x %struct.node_t_struct]* noalias "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="0", [128 x i256]* noalias readonly "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1") #3 {
entry:
  %2 = icmp eq [256 x %struct.node_t_struct]* %0, null
  %3 = icmp eq [128 x i256]* %1, null
  %4 = or i1 %2, %3
  br i1 %4, label %ret, label %copy

copy:                                             ; preds = %entry
  br label %for.loop

for.loop:                                         ; preds = %for.loop, %copy
  %for.loop.idx5 = phi i64 [ 0, %copy ], [ %for.loop.idx.next, %for.loop ]
  %5 = udiv i64 %for.loop.idx5, 128
  %6 = mul i64 128, %5
  %7 = urem i64 %for.loop.idx5, 128
  %8 = getelementptr [128 x i256], [128 x i256]* %1, i64 0, i64 %7
  %dst.addr.02 = getelementptr [256 x %struct.node_t_struct], [256 x %struct.node_t_struct]* %0, i64 0, i64 %for.loop.idx5, i32 0
  %9 = load i256, i256* %8, align 32
  %10 = zext i64 %6 to i256
  %11 = lshr i256 %9, %10
  %12 = trunc i256 %11 to i128
  %.partselect1 = trunc i128 %12 to i64
  store i64 %.partselect1, i64* %dst.addr.02, align 8
  %dst.addr.14 = getelementptr [256 x %struct.node_t_struct], [256 x %struct.node_t_struct]* %0, i64 0, i64 %for.loop.idx5, i32 1
  %13 = lshr i128 %12, 64
  %.partselect = trunc i128 %13 to i64
  store i64 %.partselect, i64* %dst.addr.14, align 8
  %for.loop.idx.next = add nuw nsw i64 %for.loop.idx5, 1
  %exitcond = icmp ne i64 %for.loop.idx.next, 256
  br i1 %exitcond, label %for.loop, label %ret

ret:                                              ; preds = %for.loop, %entry
  ret void
}

; Function Attrs: argmemonly noinline norecurse
define internal void @onebyonecpy_hls.p0a4096struct.edge_t_struct([4096 x %struct.edge_t_struct]* noalias "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="0", [2048 x i128]* noalias readonly "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1") #3 {
entry:
  %2 = icmp eq [4096 x %struct.edge_t_struct]* %0, null
  %3 = icmp eq [2048 x i128]* %1, null
  %4 = or i1 %2, %3
  br i1 %4, label %ret, label %copy

copy:                                             ; preds = %entry
  br label %for.loop

for.loop:                                         ; preds = %for.loop, %copy
  %for.loop.idx3 = phi i64 [ 0, %copy ], [ %for.loop.idx.next, %for.loop ]
  %5 = urem i64 %for.loop.idx3, 2
  %6 = mul i64 64, %5
  %7 = udiv i64 %for.loop.idx3, 2
  %8 = getelementptr [2048 x i128], [2048 x i128]* %1, i64 0, i64 %7
  %dst.addr.02 = getelementptr [4096 x %struct.edge_t_struct], [4096 x %struct.edge_t_struct]* %0, i64 0, i64 %for.loop.idx3, i32 0
  %9 = load i128, i128* %8, align 16
  %10 = zext i64 %6 to i128
  %11 = lshr i128 %9, %10
  %12 = trunc i128 %11 to i64
  store i64 %12, i64* %dst.addr.02, align 8
  %for.loop.idx.next = add nuw nsw i64 %for.loop.idx3, 1
  %exitcond = icmp ne i64 %for.loop.idx.next, 4096
  br i1 %exitcond, label %for.loop, label %ret

ret:                                              ; preds = %for.loop, %entry
  ret void
}

; Function Attrs: argmemonly noinline norecurse
define internal void @onebyonecpy_hls.p0a10i64.41.42([10 x i64]* noalias "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="0", [5 x i128]* noalias readonly align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1") #3 {
entry:
  %2 = icmp eq [10 x i64]* %0, null
  %3 = icmp eq [5 x i128]* %1, null
  %4 = or i1 %2, %3
  br i1 %4, label %ret, label %copy

copy:                                             ; preds = %entry
  br label %for.loop

for.loop:                                         ; preds = %for.loop, %copy
  %for.loop.idx1 = phi i64 [ 0, %copy ], [ %for.loop.idx.next, %for.loop ]
  %dst.addr = getelementptr [10 x i64], [10 x i64]* %0, i64 0, i64 %for.loop.idx1
  %5 = urem i64 %for.loop.idx1, 2
  %6 = mul i64 64, %5
  %7 = udiv i64 %for.loop.idx1, 2
  %src.addr1 = getelementptr [5 x i128], [5 x i128]* %1, i64 0, i64 %7
  %8 = load i128, i128* %src.addr1, align 16
  %9 = zext i64 %6 to i128
  %10 = lshr i128 %8, %9
  %11 = trunc i128 %10 to i64
  store i64 %11, i64* %dst.addr, align 8
  %for.loop.idx.next = add nuw nsw i64 %for.loop.idx1, 1
  %exitcond = icmp ne i64 %for.loop.idx.next, 10
  br i1 %exitcond, label %for.loop, label %ret

ret:                                              ; preds = %for.loop, %entry
  ret void
}

; Function Attrs: argmemonly noinline norecurse
define internal void @copy_out([256 x %struct.node_t_struct]* noalias "orig.arg.no"="0", [128 x i256]* noalias readonly "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1", [4096 x %struct.edge_t_struct]* noalias "orig.arg.no"="2", [2048 x i128]* noalias readonly "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="3", [256 x i8]* noalias "orig.arg.no"="4", [128 x i8]* noalias readonly align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="5" %_0, [128 x i8]* noalias readonly align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="5" %_1, [10 x i64]* noalias "orig.arg.no"="6", [5 x i128]* noalias readonly align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="7") #5 {
entry:
  call void @onebyonecpy_hls.p0a256struct.node_t_struct.15([256 x %struct.node_t_struct]* %0, [128 x i256]* %1)
  call void @onebyonecpy_hls.p0a4096struct.edge_t_struct([4096 x %struct.edge_t_struct]* %2, [2048 x i128]* %3)
  call void @onebyonecpy_hls.p0a256i8.9.10([256 x i8]* %4, [128 x i8]* align 512 %_0, [128 x i8]* align 512 %_1)
  call void @onebyonecpy_hls.p0a10i64.41.42([10 x i64]* %5, [5 x i128]* align 512 %6)
  ret void
}

declare void @apatb_bfs_hw([128 x i256]*, [2048 x i128]*, i64, [128 x i8]*, [128 x i8]*, [5 x i128]*)

; Function Attrs: argmemonly noinline norecurse
define internal void @copy_back([256 x %struct.node_t_struct]* noalias "orig.arg.no"="0", [128 x i256]* noalias readonly "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1", [4096 x %struct.edge_t_struct]* noalias "orig.arg.no"="2", [2048 x i128]* noalias readonly "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="3", [256 x i8]* noalias "orig.arg.no"="4", [128 x i8]* noalias readonly align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="5" %_0, [128 x i8]* noalias readonly align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="5" %_1, [10 x i64]* noalias "orig.arg.no"="6", [5 x i128]* noalias readonly align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="7") #5 {
entry:
  call void @onebyonecpy_hls.p0a256i8.9.10([256 x i8]* %4, [128 x i8]* align 512 %_0, [128 x i8]* align 512 %_1)
  call void @onebyonecpy_hls.p0a10i64.41.42([10 x i64]* %5, [5 x i128]* align 512 %6)
  ret void
}

define void @bfs_hw_stub_wrapper([128 x i256]*, [2048 x i128]*, i64, [128 x i8]*, [128 x i8]*, [5 x i128]*) #6 {
entry:
  %malloccall = tail call i8* @malloc(i64 4096)
  %6 = bitcast i8* %malloccall to [256 x %struct.node_t_struct]*
  %malloccall1 = tail call i8* @malloc(i64 32768)
  %7 = bitcast i8* %malloccall1 to [4096 x %struct.edge_t_struct]*
  %8 = alloca [256 x i8]
  %9 = alloca [10 x i64]
  call void @copy_out([256 x %struct.node_t_struct]* %6, [128 x i256]* %0, [4096 x %struct.edge_t_struct]* %7, [2048 x i128]* %1, [256 x i8]* %8, [128 x i8]* %3, [128 x i8]* %4, [10 x i64]* %9, [5 x i128]* %5)
  %10 = bitcast [256 x %struct.node_t_struct]* %6 to %struct.node_t_struct*
  %11 = bitcast [4096 x %struct.edge_t_struct]* %7 to %struct.edge_t_struct*
  %12 = bitcast [256 x i8]* %8 to i8*
  %13 = bitcast [10 x i64]* %9 to i64*
  call void @bfs_hw_stub(%struct.node_t_struct* %10, %struct.edge_t_struct* %11, i64 %2, i8* %12, i64* %13)
  call void @copy_in([256 x %struct.node_t_struct]* %6, [128 x i256]* %0, [4096 x %struct.edge_t_struct]* %7, [2048 x i128]* %1, [256 x i8]* %8, [128 x i8]* %3, [128 x i8]* %4, [10 x i64]* %9, [5 x i128]* %5)
  ret void
}

declare void @bfs_hw_stub(%struct.node_t_struct*, %struct.edge_t_struct*, i64, i8*, i64*)

attributes #0 = { inaccessiblememonly nounwind }
attributes #1 = { noinline "fpga.wrapper.func"="wrapper" }
attributes #2 = { nounwind }
attributes #3 = { argmemonly noinline norecurse "fpga.wrapper.func"="onebyonecpy_hls" }
attributes #4 = { argmemonly noinline norecurse "fpga.wrapper.func"="copyin" }
attributes #5 = { argmemonly noinline norecurse "fpga.wrapper.func"="copyout" }
attributes #6 = { "fpga.wrapper.func"="stub" }

!llvm.dbg.cu = !{}
!llvm.ident = !{!0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0}
!llvm.module.flags = !{!1, !2, !3}
!blackbox_cfg = !{!4}

!0 = !{!"clang version 7.0.0 "}
!1 = !{i32 2, !"Dwarf Version", i32 4}
!2 = !{i32 2, !"Debug Info Version", i32 3}
!3 = !{i32 1, !"wchar_size", i32 4}
!4 = !{}
!5 = !DILocation(line: 4, column: 9, scope: !6)
!6 = !DILexicalBlockFile(scope: !8, file: !7, discriminator: 0)
!7 = !DIFile(filename: "/home/noel/Documents/HGBO-DSE-main/dse_ds/MachSuite/random_ds/bfs/bulk/p1/script/dir_75.tcl", directory: "/home/noel/Documents/HGBO-DSE-main/benchmark/MachSuite/bfs/bulk")
!8 = distinct !DISubprogram(name: "bfs", scope: !9, file: !9, line: 9, type: !10, isLocal: false, isDefinition: true, scopeLine: 12, flags: DIFlagPrototyped, isOptimized: false, unit: !38, variables: !4)
!9 = !DIFile(filename: "bfs.c", directory: "/home/noel/Documents/HGBO-DSE-main/benchmark/MachSuite/bfs/bulk")
!10 = !DISubroutineType(types: !11)
!11 = !{null, !12, !25, !30, !31, !37}
!12 = !DIDerivedType(tag: DW_TAG_pointer_type, baseType: !13, size: 64)
!13 = !DIDerivedType(tag: DW_TAG_typedef, name: "node_t", file: !14, line: 38, baseType: !15)
!14 = !DIFile(filename: "./bfs.h", directory: "/home/noel/Documents/HGBO-DSE-main/benchmark/MachSuite/bfs/bulk")
!15 = distinct !DICompositeType(tag: DW_TAG_structure_type, name: "node_t_struct", file: !14, line: 35, size: 128, elements: !16)
!16 = !{!17, !24}
!17 = !DIDerivedType(tag: DW_TAG_member, name: "edge_begin", scope: !15, file: !14, line: 36, baseType: !18, size: 64)
!18 = !DIDerivedType(tag: DW_TAG_typedef, name: "edge_index_t", file: !14, line: 25, baseType: !19)
!19 = !DIDerivedType(tag: DW_TAG_typedef, name: "uint64_t", file: !20, line: 27, baseType: !21)
!20 = !DIFile(filename: "/usr/include/x86_64-linux-gnu/bits/stdint-uintn.h", directory: "/home/noel/Documents/HGBO-DSE-main/benchmark/MachSuite/bfs/bulk")
!21 = !DIDerivedType(tag: DW_TAG_typedef, name: "__uint64_t", file: !22, line: 45, baseType: !23)
!22 = !DIFile(filename: "/usr/include/x86_64-linux-gnu/bits/types.h", directory: "/home/noel/Documents/HGBO-DSE-main/benchmark/MachSuite/bfs/bulk")
!23 = !DIBasicType(name: "long unsigned int", size: 64, encoding: DW_ATE_unsigned)
!24 = !DIDerivedType(tag: DW_TAG_member, name: "edge_end", scope: !15, file: !14, line: 37, baseType: !18, size: 64, offset: 64)
!25 = !DIDerivedType(tag: DW_TAG_pointer_type, baseType: !26, size: 64)
!26 = !DIDerivedType(tag: DW_TAG_typedef, name: "edge_t", file: !14, line: 33, baseType: !27)
!27 = distinct !DICompositeType(tag: DW_TAG_structure_type, name: "edge_t_struct", file: !14, line: 28, size: 64, elements: !28)
!28 = !{!29}
!29 = !DIDerivedType(tag: DW_TAG_member, name: "dst", scope: !27, file: !14, line: 32, baseType: !30, size: 64)
!30 = !DIDerivedType(tag: DW_TAG_typedef, name: "node_index_t", file: !14, line: 26, baseType: !19)
!31 = !DIDerivedType(tag: DW_TAG_pointer_type, baseType: !32, size: 64)
!32 = !DIDerivedType(tag: DW_TAG_typedef, name: "level_t", file: !14, line: 40, baseType: !33)
!33 = !DIDerivedType(tag: DW_TAG_typedef, name: "int8_t", file: !34, line: 24, baseType: !35)
!34 = !DIFile(filename: "/usr/include/x86_64-linux-gnu/bits/stdint-intn.h", directory: "/home/noel/Documents/HGBO-DSE-main/benchmark/MachSuite/bfs/bulk")
!35 = !DIDerivedType(tag: DW_TAG_typedef, name: "__int8_t", file: !22, line: 37, baseType: !36)
!36 = !DIBasicType(name: "signed char", size: 8, encoding: DW_ATE_signed_char)
!37 = !DIDerivedType(tag: DW_TAG_pointer_type, baseType: !18, size: 64)
!38 = distinct !DICompileUnit(language: DW_LANG_C99, file: !39, producer: "clang version 7.0.0 ", isOptimized: true, runtimeVersion: 0, emissionKind: FullDebug, enums: !4)
!39 = !DIFile(filename: "/home/noel/Documents/HGBO-DSE-main/benchmark/MachSuite/bfs/bulk/bfs_random_prj_p1/solution/.autopilot/db/bfs.pp.0.c", directory: "/home/noel/Documents/HGBO-DSE-main/benchmark/MachSuite/bfs/bulk")
!40 = !DILocation(line: 5, column: 9, scope: !6)
!41 = !DILocation(line: 6, column: 9, scope: !6)
!42 = !DILocation(line: 7, column: 9, scope: !6)
