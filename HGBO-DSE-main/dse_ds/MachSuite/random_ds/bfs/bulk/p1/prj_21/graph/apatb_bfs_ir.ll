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
  %malloccall_0 = call i8* @malloc(i64 2048)
  %nodes_copy_02 = bitcast i8* %malloccall_0 to [64 x i256]*
  %malloccall_1 = call i8* @malloc(i64 2048)
  %nodes_copy_13 = bitcast i8* %malloccall_1 to [64 x i256]*
  %malloccall1 = call i8* @malloc(i64 32768)
  %edges_copy = bitcast i8* %malloccall1 to [4096 x i64]*
  %level_copy_04 = alloca [64 x i16], align 512
  %level_copy_15 = alloca [64 x i16], align 512
  %level_counts_copy_06 = alloca [3 x i128], align 512
  %level_counts_copy_17 = alloca [3 x i128], align 512
  %0 = bitcast %struct.node_t_struct* %nodes to [256 x %struct.node_t_struct]*
  %1 = bitcast %struct.edge_t_struct* %edges to [4096 x %struct.edge_t_struct]*
  %2 = bitcast i8* %level to [256 x i8]*
  %3 = bitcast i64* %level_counts to [10 x i64]*
  call void @copy_in([256 x %struct.node_t_struct]* nonnull %0, [64 x i256]* %nodes_copy_02, [64 x i256]* %nodes_copy_13, [4096 x %struct.edge_t_struct]* nonnull %1, [4096 x i64]* %edges_copy, [256 x i8]* nonnull %2, [64 x i16]* nonnull align 512 %level_copy_04, [64 x i16]* nonnull align 512 %level_copy_15, [10 x i64]* nonnull %3, [3 x i128]* nonnull align 512 %level_counts_copy_06, [3 x i128]* nonnull align 512 %level_counts_copy_17)
  %4 = getelementptr [64 x i256], [64 x i256]* %nodes_copy_02, i32 0, i32 0
  %5 = getelementptr [64 x i256], [64 x i256]* %nodes_copy_13, i32 0, i32 0
  %6 = getelementptr [4096 x i64], [4096 x i64]* %edges_copy, i32 0, i32 0
  %level_copy.gep_08 = getelementptr [64 x i16], [64 x i16]* %level_copy_04, i64 0, i32 0
  %level_copy.gep_19 = getelementptr [64 x i16], [64 x i16]* %level_copy_15, i64 0, i32 0
  %level_counts_copy.gep_010 = getelementptr [3 x i128], [3 x i128]* %level_counts_copy_06, i64 0, i32 0
  %level_counts_copy.gep_111 = getelementptr [3 x i128], [3 x i128]* %level_counts_copy_17, i64 0, i32 0
  call void @llvm.sideeffect() #7 [ "xlx_array_partition"(i256* %4, i32 0, i32 1, i32 0, i1 false) ], !dbg !5
  call void @llvm.sideeffect() #7 [ "xlx_array_partition"(i256* %5, i32 0, i32 1, i32 0, i1 false) ], !dbg !5
  call void @llvm.sideeffect() #8 [ "xlx_array_partition"(i16* %level_copy.gep_08, i32 0, i32 1, i32 0, i1 false) ], !dbg !40
  call void @llvm.sideeffect() #8 [ "xlx_array_partition"(i16* %level_copy.gep_19, i32 0, i32 1, i32 0, i1 false) ], !dbg !40
  call void @llvm.sideeffect() #9 [ "xlx_array_partition"(i128* %level_counts_copy.gep_010, i32 0, i32 1, i32 0, i1 false) ], !dbg !41
  call void @llvm.sideeffect() #9 [ "xlx_array_partition"(i128* %level_counts_copy.gep_111, i32 0, i32 1, i32 0, i1 false) ], !dbg !41
  call void @apatb_bfs_hw([64 x i256]* %nodes_copy_02, [64 x i256]* %nodes_copy_13, i64* %6, i64 %starting_node, [64 x i16]* %level_copy_04, [64 x i16]* %level_copy_15, [3 x i128]* %level_counts_copy_06, [3 x i128]* %level_counts_copy_17)
  call void @copy_back([256 x %struct.node_t_struct]* %0, [64 x i256]* %nodes_copy_02, [64 x i256]* %nodes_copy_13, [4096 x %struct.edge_t_struct]* %1, [4096 x i64]* %edges_copy, [256 x i8]* %2, [64 x i16]* %level_copy_04, [64 x i16]* %level_copy_15, [10 x i64]* %3, [3 x i128]* %level_counts_copy_06, [3 x i128]* %level_counts_copy_17)
  call void @free(i8* %malloccall_0)
  call void @free(i8* %malloccall_1)
  call void @free(i8* %malloccall1)
  call void @llvm.sideeffect() #0 [ "xlx_array_reshape"(i256* %4, i32 0, i32 1, i32 0) ]
  call void @llvm.sideeffect() #0 [ "xlx_array_reshape"(i256* %5, i32 0, i32 1, i32 0) ]
  call void @llvm.sideeffect() #0 [ "xlx_array_reshape"(i16* %level_copy.gep_08, i32 0, i32 1, i32 0) ]
  call void @llvm.sideeffect() #0 [ "xlx_array_reshape"(i16* %level_copy.gep_19, i32 0, i32 1, i32 0) ]
  call void @llvm.sideeffect() #0 [ "xlx_array_reshape"(i128* %level_counts_copy.gep_010, i32 0, i32 1, i32 0) ]
  call void @llvm.sideeffect() #0 [ "xlx_array_reshape"(i128* %level_counts_copy.gep_111, i32 0, i32 1, i32 0) ]
  ret void
}

declare noalias i8* @malloc(i64) local_unnamed_addr

; Function Attrs: argmemonly noinline norecurse
define internal fastcc void @onebyonecpy_hls.p0a4096struct.edge_t_struct([4096 x i64]* noalias, [4096 x %struct.edge_t_struct]* noalias readonly) unnamed_addr #2 {
entry:
  %2 = icmp eq [4096 x i64]* %0, null
  %3 = icmp eq [4096 x %struct.edge_t_struct]* %1, null
  %4 = or i1 %2, %3
  br i1 %4, label %ret, label %copy

copy:                                             ; preds = %entry
  br label %for.loop

for.loop:                                         ; preds = %for.loop, %copy
  %for.loop.idx3 = phi i64 [ 0, %copy ], [ %for.loop.idx.next, %for.loop ]
  %src.addr.01 = getelementptr [4096 x %struct.edge_t_struct], [4096 x %struct.edge_t_struct]* %1, i64 0, i64 %for.loop.idx3, i32 0
  %5 = getelementptr [4096 x i64], [4096 x i64]* %0, i64 0, i64 %for.loop.idx3
  %6 = load i64, i64* %src.addr.01, align 8
  store i64 %6, i64* %5, align 8
  %for.loop.idx.next = add nuw nsw i64 %for.loop.idx3, 1
  %exitcond = icmp ne i64 %for.loop.idx.next, 4096
  br i1 %exitcond, label %for.loop, label %ret

ret:                                              ; preds = %for.loop, %entry
  ret void
}

declare void @free(i8*) local_unnamed_addr

; Function Attrs: nounwind
declare void @llvm.assume(i1) #3

; Function Attrs: argmemonly noinline norecurse
define internal fastcc void @onebyonecpy_hls.p0a4096struct.edge_t_struct.23([4096 x %struct.edge_t_struct]* noalias, [4096 x i64]* noalias readonly) unnamed_addr #2 {
entry:
  %2 = icmp eq [4096 x %struct.edge_t_struct]* %0, null
  %3 = icmp eq [4096 x i64]* %1, null
  %4 = or i1 %2, %3
  br i1 %4, label %ret, label %copy

copy:                                             ; preds = %entry
  br label %for.loop

for.loop:                                         ; preds = %for.loop, %copy
  %for.loop.idx3 = phi i64 [ 0, %copy ], [ %for.loop.idx.next, %for.loop ]
  %5 = getelementptr [4096 x i64], [4096 x i64]* %1, i64 0, i64 %for.loop.idx3
  %dst.addr.02 = getelementptr [4096 x %struct.edge_t_struct], [4096 x %struct.edge_t_struct]* %0, i64 0, i64 %for.loop.idx3, i32 0
  %6 = load i64, i64* %5, align 8
  store i64 %6, i64* %dst.addr.02, align 8
  %for.loop.idx.next = add nuw nsw i64 %for.loop.idx3, 1
  %exitcond = icmp ne i64 %for.loop.idx.next, 4096
  br i1 %exitcond, label %for.loop, label %ret

ret:                                              ; preds = %for.loop, %entry
  ret void
}

; Function Attrs: argmemonly noinline norecurse
define internal void @onebyonecpy_hls.p0a256struct.node_t_struct.3.4([64 x i256]* noalias "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="0" %_0, [64 x i256]* noalias "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="0" %_1, [256 x %struct.node_t_struct]* noalias readonly "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1") #2 {
entry:
  %1 = icmp eq [64 x i256]* %_0, null
  %2 = icmp eq [256 x %struct.node_t_struct]* %0, null
  %3 = or i1 %1, %2
  br i1 %3, label %ret, label %copy

copy:                                             ; preds = %entry
  br label %for.loop

for.loop:                                         ; preds = %dst.addr.14.exit, %copy
  %for.loop.idx5 = phi i64 [ 0, %copy ], [ %for.loop.idx.next, %dst.addr.14.exit ]
  %src.addr.01 = getelementptr [256 x %struct.node_t_struct], [256 x %struct.node_t_struct]* %0, i64 0, i64 %for.loop.idx5, i32 0
  %4 = udiv i64 %for.loop.idx5, 128
  %5 = urem i64 %for.loop.idx5, 128
  %6 = udiv i64 %5, 64
  %7 = mul i64 128, %6
  %8 = urem i64 %5, 64
  %9 = getelementptr [64 x i256], [64 x i256]* %_0, i64 0, i64 %8
  %10 = getelementptr [64 x i256], [64 x i256]* %_1, i64 0, i64 %8
  %11 = load i64, i64* %src.addr.01, align 8
  %12 = trunc i64 %4 to i1
  %cond = icmp eq i1 %12, false
  %src.addr.132 = getelementptr [256 x %struct.node_t_struct], [256 x %struct.node_t_struct]* %0, i64 0, i64 %for.loop.idx5, i32 1
  %13 = load i64, i64* %src.addr.132, align 8
  %14 = zext i64 %11 to i128
  %15 = zext i64 %13 to i128
  %16 = shl i128 %15, 64
  %.partset = or i128 %16, %14
  %17 = zext i64 %7 to i256
  %18 = shl i256 340282366920938463463374607431768211455, %17
  %19 = zext i128 %.partset to i256
  %20 = shl i256 %19, %17
  %21 = xor i256 %18, -1
  br i1 %cond, label %dst.addr.14.case.0, label %dst.addr.14.case.1

dst.addr.14.case.0:                               ; preds = %for.loop
  %22 = load i256, i256* %9, align 32
  %23 = and i256 %22, %21
  %24 = or i256 %23, %20
  store i256 %24, i256* %9, align 32
  br label %dst.addr.14.exit

dst.addr.14.case.1:                               ; preds = %for.loop
  call void @llvm.assume(i1 %12)
  %25 = load i256, i256* %10, align 32
  %26 = and i256 %25, %21
  %27 = or i256 %26, %20
  store i256 %27, i256* %10, align 32
  br label %dst.addr.14.exit

dst.addr.14.exit:                                 ; preds = %dst.addr.14.case.1, %dst.addr.14.case.0
  %for.loop.idx.next = add nuw nsw i64 %for.loop.idx5, 1
  %exitcond = icmp ne i64 %for.loop.idx.next, 256
  br i1 %exitcond, label %for.loop, label %ret

ret:                                              ; preds = %dst.addr.14.exit, %entry
  ret void
}

; Function Attrs: argmemonly noinline norecurse
define internal void @onebyonecpy_hls.p0a256i8.5.6([64 x i16]* noalias align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="0" %_0, [64 x i16]* noalias align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="0" %_1, [256 x i8]* noalias readonly "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1") #2 {
entry:
  %1 = icmp eq [64 x i16]* %_0, null
  %2 = icmp eq [256 x i8]* %0, null
  %3 = or i1 %1, %2
  br i1 %3, label %ret, label %copy

copy:                                             ; preds = %entry
  br label %for.loop

for.loop:                                         ; preds = %dst.addr.exit, %copy
  %for.loop.idx1 = phi i64 [ 0, %copy ], [ %for.loop.idx.next, %dst.addr.exit ]
  %4 = urem i64 %for.loop.idx1, 2
  %5 = udiv i64 %for.loop.idx1, 2
  %6 = udiv i64 %5, 64
  %7 = mul i64 8, %6
  %8 = urem i64 %5, 64
  %dst.addr_01 = getelementptr [64 x i16], [64 x i16]* %_0, i64 0, i64 %8
  %dst.addr_12 = getelementptr [64 x i16], [64 x i16]* %_1, i64 0, i64 %8
  %src.addr = getelementptr [256 x i8], [256 x i8]* %0, i64 0, i64 %for.loop.idx1
  %9 = load i8, i8* %src.addr, align 1
  %10 = trunc i64 %4 to i1
  %cond = icmp eq i1 %10, false
  %11 = trunc i64 %7 to i16
  %12 = shl i16 255, %11
  %13 = zext i8 %9 to i16
  %14 = shl i16 %13, %11
  %15 = xor i16 %12, -1
  br i1 %cond, label %dst.addr.case.0, label %dst.addr.case.1

dst.addr.case.0:                                  ; preds = %for.loop
  %16 = load i16, i16* %dst.addr_01, align 2
  %17 = and i16 %16, %15
  %18 = or i16 %17, %14
  store i16 %18, i16* %dst.addr_01, align 2
  br label %dst.addr.exit

dst.addr.case.1:                                  ; preds = %for.loop
  call void @llvm.assume(i1 %10)
  %19 = load i16, i16* %dst.addr_12, align 2
  %20 = and i16 %19, %15
  %21 = or i16 %20, %14
  store i16 %21, i16* %dst.addr_12, align 2
  br label %dst.addr.exit

dst.addr.exit:                                    ; preds = %dst.addr.case.1, %dst.addr.case.0
  %for.loop.idx.next = add nuw nsw i64 %for.loop.idx1, 1
  %exitcond = icmp ne i64 %for.loop.idx.next, 256
  br i1 %exitcond, label %for.loop, label %ret

ret:                                              ; preds = %dst.addr.exit, %entry
  ret void
}

; Function Attrs: argmemonly noinline norecurse
define internal void @onebyonecpy_hls.p0a10i64.7.8([3 x i128]* noalias align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="0" %_0, [3 x i128]* noalias align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="0" %_1, [10 x i64]* noalias readonly "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1") #2 {
entry:
  %1 = icmp eq [3 x i128]* %_0, null
  %2 = icmp eq [10 x i64]* %0, null
  %3 = or i1 %1, %2
  br i1 %3, label %ret, label %copy

copy:                                             ; preds = %entry
  br label %for.loop

for.loop:                                         ; preds = %dst.addr.exit, %copy
  %for.loop.idx1 = phi i64 [ 0, %copy ], [ %for.loop.idx.next, %dst.addr.exit ]
  %4 = urem i64 %for.loop.idx1, 2
  %5 = udiv i64 %for.loop.idx1, 2
  %6 = urem i64 %5, 2
  %7 = mul i64 64, %6
  %8 = udiv i64 %5, 2
  %dst.addr_01 = getelementptr [3 x i128], [3 x i128]* %_0, i64 0, i64 %8
  %dst.addr_12 = getelementptr [3 x i128], [3 x i128]* %_1, i64 0, i64 %8
  %src.addr = getelementptr [10 x i64], [10 x i64]* %0, i64 0, i64 %for.loop.idx1
  %9 = load i64, i64* %src.addr, align 8
  %10 = trunc i64 %4 to i1
  %cond = icmp eq i1 %10, false
  %11 = zext i64 %7 to i128
  %12 = shl i128 18446744073709551615, %11
  %13 = zext i64 %9 to i128
  %14 = shl i128 %13, %11
  %15 = xor i128 %12, -1
  br i1 %cond, label %dst.addr.case.0, label %dst.addr.case.1

dst.addr.case.0:                                  ; preds = %for.loop
  %16 = load i128, i128* %dst.addr_01, align 16
  %17 = and i128 %16, %15
  %18 = or i128 %17, %14
  store i128 %18, i128* %dst.addr_01, align 16
  br label %dst.addr.exit

dst.addr.case.1:                                  ; preds = %for.loop
  call void @llvm.assume(i1 %10)
  %19 = load i128, i128* %dst.addr_12, align 16
  %20 = and i128 %19, %15
  %21 = or i128 %20, %14
  store i128 %21, i128* %dst.addr_12, align 16
  br label %dst.addr.exit

dst.addr.exit:                                    ; preds = %dst.addr.case.1, %dst.addr.case.0
  %for.loop.idx.next = add nuw nsw i64 %for.loop.idx1, 1
  %exitcond = icmp ne i64 %for.loop.idx.next, 10
  br i1 %exitcond, label %for.loop, label %ret

ret:                                              ; preds = %dst.addr.exit, %entry
  ret void
}

; Function Attrs: argmemonly noinline norecurse
define internal void @copy_in([256 x %struct.node_t_struct]* noalias readonly "orig.arg.no"="0", [64 x i256]* noalias "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1" %_0, [64 x i256]* noalias "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1" %_1, [4096 x %struct.edge_t_struct]* noalias readonly "orig.arg.no"="2", [4096 x i64]* noalias "orig.arg.no"="3", [256 x i8]* noalias readonly "orig.arg.no"="4", [64 x i16]* noalias align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="5" %_01, [64 x i16]* noalias align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="5" %_12, [10 x i64]* noalias readonly "orig.arg.no"="6", [3 x i128]* noalias align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="7" %_03, [3 x i128]* noalias align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="7" %_14) #4 {
entry:
  call void @onebyonecpy_hls.p0a256struct.node_t_struct.3.4([64 x i256]* %_0, [64 x i256]* %_1, [256 x %struct.node_t_struct]* %0)
  call fastcc void @onebyonecpy_hls.p0a4096struct.edge_t_struct([4096 x i64]* %2, [4096 x %struct.edge_t_struct]* %1)
  call void @onebyonecpy_hls.p0a256i8.5.6([64 x i16]* align 512 %_01, [64 x i16]* align 512 %_12, [256 x i8]* %3)
  call void @onebyonecpy_hls.p0a10i64.7.8([3 x i128]* align 512 %_03, [3 x i128]* align 512 %_14, [10 x i64]* %4)
  ret void
}

; Function Attrs: argmemonly noinline norecurse
define internal void @onebyonecpy_hls.p0a256struct.node_t_struct.13.14([256 x %struct.node_t_struct]* noalias "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="0", [64 x i256]* noalias readonly "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1" %_0, [64 x i256]* noalias readonly "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1" %_1) #2 {
entry:
  %1 = icmp eq [256 x %struct.node_t_struct]* %0, null
  %2 = icmp eq [64 x i256]* %_0, null
  %3 = or i1 %1, %2
  br i1 %3, label %ret, label %copy

copy:                                             ; preds = %entry
  br label %for.loop

for.loop:                                         ; preds = %src.addr.13.exit, %copy
  %for.loop.idx5 = phi i64 [ 0, %copy ], [ %for.loop.idx.next, %src.addr.13.exit ]
  %4 = udiv i64 %for.loop.idx5, 128
  %5 = urem i64 %for.loop.idx5, 128
  %6 = udiv i64 %5, 64
  %7 = mul i64 128, %6
  %8 = urem i64 %5, 64
  %9 = getelementptr [64 x i256], [64 x i256]* %_0, i64 0, i64 %8
  %10 = getelementptr [64 x i256], [64 x i256]* %_1, i64 0, i64 %8
  %dst.addr.02 = getelementptr [256 x %struct.node_t_struct], [256 x %struct.node_t_struct]* %0, i64 0, i64 %for.loop.idx5, i32 0
  %11 = trunc i64 %4 to i1
  %cond = icmp eq i1 %11, false
  %dst.addr.144 = getelementptr [256 x %struct.node_t_struct], [256 x %struct.node_t_struct]* %0, i64 0, i64 %for.loop.idx5, i32 1
  %12 = zext i64 %7 to i256
  br i1 %cond, label %src.addr.13.case.0, label %src.addr.13.case.1

src.addr.13.case.0:                               ; preds = %for.loop
  %13 = load i256, i256* %9, align 32
  %14 = lshr i256 %13, %12
  %15 = trunc i256 %14 to i128
  %_01.partselect = trunc i128 %15 to i64
  store i64 %_01.partselect, i64* %dst.addr.02, align 8
  %16 = lshr i128 %15, 64
  %_03.partselect = trunc i128 %16 to i64
  br label %src.addr.13.exit

src.addr.13.case.1:                               ; preds = %for.loop
  call void @llvm.assume(i1 %11)
  %17 = load i256, i256* %10, align 32
  %18 = lshr i256 %17, %12
  %19 = trunc i256 %18 to i128
  %_12.partselect = trunc i128 %19 to i64
  store i64 %_12.partselect, i64* %dst.addr.02, align 8
  %20 = lshr i128 %19, 64
  %_14.partselect = trunc i128 %20 to i64
  br label %src.addr.13.exit

src.addr.13.exit:                                 ; preds = %src.addr.13.case.1, %src.addr.13.case.0
  %21 = phi i64 [ %_03.partselect, %src.addr.13.case.0 ], [ %_14.partselect, %src.addr.13.case.1 ]
  store i64 %21, i64* %dst.addr.144, align 8
  %for.loop.idx.next = add nuw nsw i64 %for.loop.idx5, 1
  %exitcond = icmp ne i64 %for.loop.idx.next, 256
  br i1 %exitcond, label %for.loop, label %ret

ret:                                              ; preds = %src.addr.13.exit, %entry
  ret void
}

; Function Attrs: argmemonly noinline norecurse
define internal void @onebyonecpy_hls.p0a256i8.15.16([256 x i8]* noalias "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="0", [64 x i16]* noalias readonly align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1" %_0, [64 x i16]* noalias readonly align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1" %_1) #2 {
entry:
  %1 = icmp eq [256 x i8]* %0, null
  %2 = icmp eq [64 x i16]* %_0, null
  %3 = or i1 %1, %2
  br i1 %3, label %ret, label %copy

copy:                                             ; preds = %entry
  br label %for.loop

for.loop:                                         ; preds = %src.addr.exit, %copy
  %for.loop.idx1 = phi i64 [ 0, %copy ], [ %for.loop.idx.next, %src.addr.exit ]
  %dst.addr = getelementptr [256 x i8], [256 x i8]* %0, i64 0, i64 %for.loop.idx1
  %4 = urem i64 %for.loop.idx1, 2
  %5 = udiv i64 %for.loop.idx1, 2
  %6 = udiv i64 %5, 64
  %7 = mul i64 8, %6
  %8 = urem i64 %5, 64
  %src.addr_01 = getelementptr [64 x i16], [64 x i16]* %_0, i64 0, i64 %8
  %src.addr_12 = getelementptr [64 x i16], [64 x i16]* %_1, i64 0, i64 %8
  %9 = trunc i64 %4 to i1
  %cond = icmp eq i1 %9, false
  %10 = trunc i64 %7 to i16
  br i1 %cond, label %src.addr.case.0, label %src.addr.case.1

src.addr.case.0:                                  ; preds = %for.loop
  %_013 = load i16, i16* %src.addr_01, align 2
  %11 = lshr i16 %_013, %10
  %12 = trunc i16 %11 to i8
  br label %src.addr.exit

src.addr.case.1:                                  ; preds = %for.loop
  call void @llvm.assume(i1 %9)
  %_124 = load i16, i16* %src.addr_12, align 2
  %13 = lshr i16 %_124, %10
  %14 = trunc i16 %13 to i8
  br label %src.addr.exit

src.addr.exit:                                    ; preds = %src.addr.case.1, %src.addr.case.0
  %15 = phi i8 [ %12, %src.addr.case.0 ], [ %14, %src.addr.case.1 ]
  store i8 %15, i8* %dst.addr, align 1
  %for.loop.idx.next = add nuw nsw i64 %for.loop.idx1, 1
  %exitcond = icmp ne i64 %for.loop.idx.next, 256
  br i1 %exitcond, label %for.loop, label %ret

ret:                                              ; preds = %src.addr.exit, %entry
  ret void
}

; Function Attrs: argmemonly noinline norecurse
define internal void @onebyonecpy_hls.p0a10i64.17.18([10 x i64]* noalias "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="0", [3 x i128]* noalias readonly align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1" %_0, [3 x i128]* noalias readonly align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1" %_1) #2 {
entry:
  %1 = icmp eq [10 x i64]* %0, null
  %2 = icmp eq [3 x i128]* %_0, null
  %3 = or i1 %1, %2
  br i1 %3, label %ret, label %copy

copy:                                             ; preds = %entry
  br label %for.loop

for.loop:                                         ; preds = %src.addr.exit, %copy
  %for.loop.idx1 = phi i64 [ 0, %copy ], [ %for.loop.idx.next, %src.addr.exit ]
  %dst.addr = getelementptr [10 x i64], [10 x i64]* %0, i64 0, i64 %for.loop.idx1
  %4 = urem i64 %for.loop.idx1, 2
  %5 = udiv i64 %for.loop.idx1, 2
  %6 = urem i64 %5, 2
  %7 = mul i64 64, %6
  %8 = udiv i64 %5, 2
  %src.addr_01 = getelementptr [3 x i128], [3 x i128]* %_0, i64 0, i64 %8
  %src.addr_12 = getelementptr [3 x i128], [3 x i128]* %_1, i64 0, i64 %8
  %9 = trunc i64 %4 to i1
  %cond = icmp eq i1 %9, false
  %10 = zext i64 %7 to i128
  br i1 %cond, label %src.addr.case.0, label %src.addr.case.1

src.addr.case.0:                                  ; preds = %for.loop
  %_013 = load i128, i128* %src.addr_01, align 16
  %11 = lshr i128 %_013, %10
  %12 = trunc i128 %11 to i64
  br label %src.addr.exit

src.addr.case.1:                                  ; preds = %for.loop
  call void @llvm.assume(i1 %9)
  %_124 = load i128, i128* %src.addr_12, align 16
  %13 = lshr i128 %_124, %10
  %14 = trunc i128 %13 to i64
  br label %src.addr.exit

src.addr.exit:                                    ; preds = %src.addr.case.1, %src.addr.case.0
  %15 = phi i64 [ %12, %src.addr.case.0 ], [ %14, %src.addr.case.1 ]
  store i64 %15, i64* %dst.addr, align 8
  %for.loop.idx.next = add nuw nsw i64 %for.loop.idx1, 1
  %exitcond = icmp ne i64 %for.loop.idx.next, 10
  br i1 %exitcond, label %for.loop, label %ret

ret:                                              ; preds = %src.addr.exit, %entry
  ret void
}

; Function Attrs: argmemonly noinline norecurse
define internal void @copy_out([256 x %struct.node_t_struct]* noalias "orig.arg.no"="0", [64 x i256]* noalias readonly "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1" %_0, [64 x i256]* noalias readonly "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1" %_1, [4096 x %struct.edge_t_struct]* noalias "orig.arg.no"="2", [4096 x i64]* noalias readonly "orig.arg.no"="3", [256 x i8]* noalias "orig.arg.no"="4", [64 x i16]* noalias readonly align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="5" %_01, [64 x i16]* noalias readonly align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="5" %_12, [10 x i64]* noalias "orig.arg.no"="6", [3 x i128]* noalias readonly align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="7" %_03, [3 x i128]* noalias readonly align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="7" %_14) #5 {
entry:
  call void @onebyonecpy_hls.p0a256struct.node_t_struct.13.14([256 x %struct.node_t_struct]* %0, [64 x i256]* %_0, [64 x i256]* %_1)
  call fastcc void @onebyonecpy_hls.p0a4096struct.edge_t_struct.23([4096 x %struct.edge_t_struct]* %1, [4096 x i64]* %2)
  call void @onebyonecpy_hls.p0a256i8.15.16([256 x i8]* %3, [64 x i16]* align 512 %_01, [64 x i16]* align 512 %_12)
  call void @onebyonecpy_hls.p0a10i64.17.18([10 x i64]* %4, [3 x i128]* align 512 %_03, [3 x i128]* align 512 %_14)
  ret void
}

declare void @apatb_bfs_hw([64 x i256]*, [64 x i256]*, i64*, i64, [64 x i16]*, [64 x i16]*, [3 x i128]*, [3 x i128]*)

; Function Attrs: argmemonly noinline norecurse
define internal void @copy_back([256 x %struct.node_t_struct]* noalias "orig.arg.no"="0", [64 x i256]* noalias readonly "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1" %_0, [64 x i256]* noalias readonly "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="1" %_1, [4096 x %struct.edge_t_struct]* noalias "orig.arg.no"="2", [4096 x i64]* noalias readonly "orig.arg.no"="3", [256 x i8]* noalias "orig.arg.no"="4", [64 x i16]* noalias readonly align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="5" %_01, [64 x i16]* noalias readonly align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="5" %_12, [10 x i64]* noalias "orig.arg.no"="6", [3 x i128]* noalias readonly align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="7" %_03, [3 x i128]* noalias readonly align 512 "fpga.caller.interfaces"="layout_transformed" "orig.arg.no"="7" %_14) #5 {
entry:
  call void @onebyonecpy_hls.p0a256i8.15.16([256 x i8]* %3, [64 x i16]* align 512 %_01, [64 x i16]* align 512 %_12)
  call void @onebyonecpy_hls.p0a10i64.17.18([10 x i64]* %4, [3 x i128]* align 512 %_03, [3 x i128]* align 512 %_14)
  ret void
}

define void @bfs_hw_stub_wrapper([64 x i256]*, [64 x i256]*, i64*, i64, [64 x i16]*, [64 x i16]*, [3 x i128]*, [3 x i128]*) #6 {
entry:
  %malloccall = tail call i8* @malloc(i64 4096)
  %8 = bitcast i8* %malloccall to [256 x %struct.node_t_struct]*
  %malloccall1 = tail call i8* @malloc(i64 32768)
  %9 = bitcast i8* %malloccall1 to [4096 x %struct.edge_t_struct]*
  %10 = alloca [256 x i8]
  %11 = alloca [10 x i64]
  %12 = bitcast i64* %2 to [4096 x i64]*
  call void @copy_out([256 x %struct.node_t_struct]* %8, [64 x i256]* %0, [64 x i256]* %1, [4096 x %struct.edge_t_struct]* %9, [4096 x i64]* %12, [256 x i8]* %10, [64 x i16]* %4, [64 x i16]* %5, [10 x i64]* %11, [3 x i128]* %6, [3 x i128]* %7)
  %13 = bitcast [256 x %struct.node_t_struct]* %8 to %struct.node_t_struct*
  %14 = bitcast [4096 x %struct.edge_t_struct]* %9 to %struct.edge_t_struct*
  %15 = bitcast [256 x i8]* %10 to i8*
  %16 = bitcast [10 x i64]* %11 to i64*
  call void @bfs_hw_stub(%struct.node_t_struct* %13, %struct.edge_t_struct* %14, i64 %3, i8* %15, i64* %16)
  call void @copy_in([256 x %struct.node_t_struct]* %8, [64 x i256]* %0, [64 x i256]* %1, [4096 x %struct.edge_t_struct]* %9, [4096 x i64]* %12, [256 x i8]* %10, [64 x i16]* %4, [64 x i16]* %5, [10 x i64]* %11, [3 x i128]* %6, [3 x i128]* %7)
  ret void
}

declare void @bfs_hw_stub(%struct.node_t_struct*, %struct.edge_t_struct*, i64, i8*, i64*)

attributes #0 = { inaccessiblememonly nounwind }
attributes #1 = { noinline "fpga.wrapper.func"="wrapper" }
attributes #2 = { argmemonly noinline norecurse "fpga.wrapper.func"="onebyonecpy_hls" }
attributes #3 = { nounwind }
attributes #4 = { argmemonly noinline norecurse "fpga.wrapper.func"="copyin" }
attributes #5 = { argmemonly noinline norecurse "fpga.wrapper.func"="copyout" }
attributes #6 = { "fpga.wrapper.func"="stub" }
attributes #7 = { inaccessiblememonly nounwind "xlx.port.bitwidth"="144115188075855871" }
attributes #8 = { inaccessiblememonly nounwind "xlx.port.bitwidth"="2305843009213693951" }
attributes #9 = { inaccessiblememonly nounwind "xlx.port.bitwidth"="288230376151711743" }

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
!7 = !DIFile(filename: "/home/noel/Documents/HGBO-DSE-main/dse_ds/MachSuite/random_ds/bfs/bulk/p1/script/dir_21.tcl", directory: "/home/noel/Documents/HGBO-DSE-main/benchmark/MachSuite/bfs/bulk")
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
!40 = !DILocation(line: 6, column: 9, scope: !6)
!41 = !DILocation(line: 8, column: 9, scope: !6)
