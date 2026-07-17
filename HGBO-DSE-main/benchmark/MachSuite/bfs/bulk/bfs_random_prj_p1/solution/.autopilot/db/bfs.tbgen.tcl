set moduleName bfs
set isTopModule 1
set isCombinational 0
set isDatapathOnly 0
set isPipelined 0
set pipeline_type none
set FunctionProtocol ap_ctrl_hs
set isOneStateSeq 0
set ProfileFlag 0
set StallSigGenFlag 0
set isEnableWaveformDebug 1
set hasInterrupt 0
set C_modelName {bfs}
set C_modelType { void 0 }
set C_modelArgList {
	{ nodes int 128 regular {array 256 { 1 3 } 1 1 }  }
	{ edges_0 int 128 regular {array 1024 { 1 3 } 1 1 }  }
	{ edges_1 int 128 regular {array 1024 { 1 3 } 1 1 }  }
	{ starting_node int 64 regular  }
	{ level_0 int 8 regular {array 128 { 2 3 } 1 1 }  }
	{ level_1 int 8 regular {array 128 { 2 3 } 1 1 }  }
	{ level_counts int 64 regular {array 10 { 0 3 } 0 1 }  }
}
set C_modelArgMapList {[ 
	{ "Name" : "nodes", "interface" : "memory", "bitwidth" : 128, "direction" : "READONLY"} , 
 	{ "Name" : "edges_0", "interface" : "memory", "bitwidth" : 128, "direction" : "READONLY"} , 
 	{ "Name" : "edges_1", "interface" : "memory", "bitwidth" : 128, "direction" : "READONLY"} , 
 	{ "Name" : "starting_node", "interface" : "wire", "bitwidth" : 64, "direction" : "READONLY"} , 
 	{ "Name" : "level_0", "interface" : "memory", "bitwidth" : 8, "direction" : "READWRITE"} , 
 	{ "Name" : "level_1", "interface" : "memory", "bitwidth" : 8, "direction" : "READWRITE"} , 
 	{ "Name" : "level_counts", "interface" : "memory", "bitwidth" : 64, "direction" : "WRITEONLY"} ]}
# RTL Port declarations: 
set portNum 30
set portList { 
	{ ap_clk sc_in sc_logic 1 clock -1 } 
	{ ap_rst sc_in sc_logic 1 reset -1 active_high_sync } 
	{ ap_start sc_in sc_logic 1 start -1 } 
	{ ap_done sc_out sc_logic 1 predone -1 } 
	{ ap_idle sc_out sc_logic 1 done -1 } 
	{ ap_ready sc_out sc_logic 1 ready -1 } 
	{ nodes_address0 sc_out sc_lv 8 signal 0 } 
	{ nodes_ce0 sc_out sc_logic 1 signal 0 } 
	{ nodes_q0 sc_in sc_lv 128 signal 0 } 
	{ edges_0_address0 sc_out sc_lv 10 signal 1 } 
	{ edges_0_ce0 sc_out sc_logic 1 signal 1 } 
	{ edges_0_q0 sc_in sc_lv 128 signal 1 } 
	{ edges_1_address0 sc_out sc_lv 10 signal 2 } 
	{ edges_1_ce0 sc_out sc_logic 1 signal 2 } 
	{ edges_1_q0 sc_in sc_lv 128 signal 2 } 
	{ starting_node sc_in sc_lv 64 signal 3 } 
	{ level_0_address0 sc_out sc_lv 7 signal 4 } 
	{ level_0_ce0 sc_out sc_logic 1 signal 4 } 
	{ level_0_we0 sc_out sc_logic 1 signal 4 } 
	{ level_0_d0 sc_out sc_lv 8 signal 4 } 
	{ level_0_q0 sc_in sc_lv 8 signal 4 } 
	{ level_1_address0 sc_out sc_lv 7 signal 5 } 
	{ level_1_ce0 sc_out sc_logic 1 signal 5 } 
	{ level_1_we0 sc_out sc_logic 1 signal 5 } 
	{ level_1_d0 sc_out sc_lv 8 signal 5 } 
	{ level_1_q0 sc_in sc_lv 8 signal 5 } 
	{ level_counts_address0 sc_out sc_lv 4 signal 6 } 
	{ level_counts_ce0 sc_out sc_logic 1 signal 6 } 
	{ level_counts_we0 sc_out sc_logic 1 signal 6 } 
	{ level_counts_d0 sc_out sc_lv 64 signal 6 } 
}
set NewPortList {[ 
	{ "name": "ap_clk", "direction": "in", "datatype": "sc_logic", "bitwidth":1, "type": "clock", "bundle":{"name": "ap_clk", "role": "default" }} , 
 	{ "name": "ap_rst", "direction": "in", "datatype": "sc_logic", "bitwidth":1, "type": "reset", "bundle":{"name": "ap_rst", "role": "default" }} , 
 	{ "name": "ap_start", "direction": "in", "datatype": "sc_logic", "bitwidth":1, "type": "start", "bundle":{"name": "ap_start", "role": "default" }} , 
 	{ "name": "ap_done", "direction": "out", "datatype": "sc_logic", "bitwidth":1, "type": "predone", "bundle":{"name": "ap_done", "role": "default" }} , 
 	{ "name": "ap_idle", "direction": "out", "datatype": "sc_logic", "bitwidth":1, "type": "done", "bundle":{"name": "ap_idle", "role": "default" }} , 
 	{ "name": "ap_ready", "direction": "out", "datatype": "sc_logic", "bitwidth":1, "type": "ready", "bundle":{"name": "ap_ready", "role": "default" }} , 
 	{ "name": "nodes_address0", "direction": "out", "datatype": "sc_lv", "bitwidth":8, "type": "signal", "bundle":{"name": "nodes", "role": "address0" }} , 
 	{ "name": "nodes_ce0", "direction": "out", "datatype": "sc_logic", "bitwidth":1, "type": "signal", "bundle":{"name": "nodes", "role": "ce0" }} , 
 	{ "name": "nodes_q0", "direction": "in", "datatype": "sc_lv", "bitwidth":128, "type": "signal", "bundle":{"name": "nodes", "role": "q0" }} , 
 	{ "name": "edges_0_address0", "direction": "out", "datatype": "sc_lv", "bitwidth":10, "type": "signal", "bundle":{"name": "edges_0", "role": "address0" }} , 
 	{ "name": "edges_0_ce0", "direction": "out", "datatype": "sc_logic", "bitwidth":1, "type": "signal", "bundle":{"name": "edges_0", "role": "ce0" }} , 
 	{ "name": "edges_0_q0", "direction": "in", "datatype": "sc_lv", "bitwidth":128, "type": "signal", "bundle":{"name": "edges_0", "role": "q0" }} , 
 	{ "name": "edges_1_address0", "direction": "out", "datatype": "sc_lv", "bitwidth":10, "type": "signal", "bundle":{"name": "edges_1", "role": "address0" }} , 
 	{ "name": "edges_1_ce0", "direction": "out", "datatype": "sc_logic", "bitwidth":1, "type": "signal", "bundle":{"name": "edges_1", "role": "ce0" }} , 
 	{ "name": "edges_1_q0", "direction": "in", "datatype": "sc_lv", "bitwidth":128, "type": "signal", "bundle":{"name": "edges_1", "role": "q0" }} , 
 	{ "name": "starting_node", "direction": "in", "datatype": "sc_lv", "bitwidth":64, "type": "signal", "bundle":{"name": "starting_node", "role": "default" }} , 
 	{ "name": "level_0_address0", "direction": "out", "datatype": "sc_lv", "bitwidth":7, "type": "signal", "bundle":{"name": "level_0", "role": "address0" }} , 
 	{ "name": "level_0_ce0", "direction": "out", "datatype": "sc_logic", "bitwidth":1, "type": "signal", "bundle":{"name": "level_0", "role": "ce0" }} , 
 	{ "name": "level_0_we0", "direction": "out", "datatype": "sc_logic", "bitwidth":1, "type": "signal", "bundle":{"name": "level_0", "role": "we0" }} , 
 	{ "name": "level_0_d0", "direction": "out", "datatype": "sc_lv", "bitwidth":8, "type": "signal", "bundle":{"name": "level_0", "role": "d0" }} , 
 	{ "name": "level_0_q0", "direction": "in", "datatype": "sc_lv", "bitwidth":8, "type": "signal", "bundle":{"name": "level_0", "role": "q0" }} , 
 	{ "name": "level_1_address0", "direction": "out", "datatype": "sc_lv", "bitwidth":7, "type": "signal", "bundle":{"name": "level_1", "role": "address0" }} , 
 	{ "name": "level_1_ce0", "direction": "out", "datatype": "sc_logic", "bitwidth":1, "type": "signal", "bundle":{"name": "level_1", "role": "ce0" }} , 
 	{ "name": "level_1_we0", "direction": "out", "datatype": "sc_logic", "bitwidth":1, "type": "signal", "bundle":{"name": "level_1", "role": "we0" }} , 
 	{ "name": "level_1_d0", "direction": "out", "datatype": "sc_lv", "bitwidth":8, "type": "signal", "bundle":{"name": "level_1", "role": "d0" }} , 
 	{ "name": "level_1_q0", "direction": "in", "datatype": "sc_lv", "bitwidth":8, "type": "signal", "bundle":{"name": "level_1", "role": "q0" }} , 
 	{ "name": "level_counts_address0", "direction": "out", "datatype": "sc_lv", "bitwidth":4, "type": "signal", "bundle":{"name": "level_counts", "role": "address0" }} , 
 	{ "name": "level_counts_ce0", "direction": "out", "datatype": "sc_logic", "bitwidth":1, "type": "signal", "bundle":{"name": "level_counts", "role": "ce0" }} , 
 	{ "name": "level_counts_we0", "direction": "out", "datatype": "sc_logic", "bitwidth":1, "type": "signal", "bundle":{"name": "level_counts", "role": "we0" }} , 
 	{ "name": "level_counts_d0", "direction": "out", "datatype": "sc_lv", "bitwidth":64, "type": "signal", "bundle":{"name": "level_counts", "role": "d0" }}  ]}

set RtlHierarchyInfo {[
	{"ID" : "0", "Level" : "0", "Path" : "`AUTOTB_DUT_INST", "Parent" : "", "Child" : ["1", "2", "3"],
		"CDFG" : "bfs",
		"Protocol" : "ap_ctrl_hs",
		"ControlExist" : "1", "ap_start" : "1", "ap_ready" : "1", "ap_done" : "1", "ap_continue" : "0", "ap_idle" : "1", "real_start" : "0",
		"Pipeline" : "None", "UnalignedPipeline" : "0", "RewindPipeline" : "0", "ProcessNetwork" : "0",
		"II" : "0",
		"VariableLatency" : "1", "ExactLatency" : "-1", "EstimateLatencyMin" : "-1", "EstimateLatencyMax" : "-1",
		"Combinational" : "0",
		"Datapath" : "0",
		"ClockEnable" : "0",
		"HasSubDataflow" : "0",
		"InDataflowNetwork" : "0",
		"HasNonBlockingOperation" : "0",
		"IsBlackBox" : "0",
		"Port" : [
			{"Name" : "nodes", "Type" : "Memory", "Direction" : "I"},
			{"Name" : "edges_0", "Type" : "Memory", "Direction" : "I"},
			{"Name" : "edges_1", "Type" : "Memory", "Direction" : "I"},
			{"Name" : "starting_node", "Type" : "None", "Direction" : "I"},
			{"Name" : "level_0", "Type" : "Memory", "Direction" : "IO"},
			{"Name" : "level_1", "Type" : "Memory", "Direction" : "IO"},
			{"Name" : "level_counts", "Type" : "Memory", "Direction" : "O"}],
		"Loop" : [
			{"Name" : "loop_neighbors", "PipelineType" : "no",
				"LoopDec" : {"FSMBitwidth" : "10", "FirstState" : "ap_ST_fsm_state6", "LastState" : ["ap_ST_fsm_state9"], "QuitState" : ["ap_ST_fsm_state6"], "PreState" : ["ap_ST_fsm_state5"], "PostState" : ["ap_ST_fsm_state10"], "OneDepthLoop" : "0", "OneStateBlock": ""}},
			{"Name" : "loop_nodes", "PipelineType" : "no",
				"LoopDec" : {"FSMBitwidth" : "10", "FirstState" : "ap_ST_fsm_state3", "LastState" : ["ap_ST_fsm_state10"], "QuitState" : ["ap_ST_fsm_state3"], "PreState" : ["ap_ST_fsm_state2"], "PostState" : ["ap_ST_fsm_state2"], "OneDepthLoop" : "0", "OneStateBlock": ""}},
			{"Name" : "loop_horizons", "PipelineType" : "no",
				"LoopDec" : {"FSMBitwidth" : "10", "FirstState" : "ap_ST_fsm_state2", "LastState" : ["ap_ST_fsm_state3"], "QuitState" : ["ap_ST_fsm_state2"], "PreState" : ["ap_ST_fsm_state1"], "PostState" : ["ap_ST_fsm_state1"], "OneDepthLoop" : "0", "OneStateBlock": ""}}]},
	{"ID" : "1", "Level" : "1", "Path" : "`AUTOTB_DUT_INST.mux_21_8_1_1_U1", "Parent" : "0"},
	{"ID" : "2", "Level" : "1", "Path" : "`AUTOTB_DUT_INST.mux_253_64_1_1_U2", "Parent" : "0"},
	{"ID" : "3", "Level" : "1", "Path" : "`AUTOTB_DUT_INST.mux_21_8_1_1_U3", "Parent" : "0"}]}


set ArgLastReadFirstWriteLatency {
	bfs {
		nodes {Type I LastRead 3 FirstWrite -1}
		edges_0 {Type I LastRead 5 FirstWrite -1}
		edges_1 {Type I LastRead 5 FirstWrite -1}
		starting_node {Type I LastRead 0 FirstWrite -1}
		level_0 {Type IO LastRead 7 FirstWrite 0}
		level_1 {Type IO LastRead 7 FirstWrite 0}
		level_counts {Type O LastRead -1 FirstWrite 0}}}

set hasDtUnsupportedChannel 0

set PerformanceInfo {[
	{"Name" : "Latency", "Min" : "-1", "Max" : "-1"}
	, {"Name" : "Interval", "Min" : "0", "Max" : "0"}
]}

set PipelineEnableSignalInfo {[
]}

set Spec2ImplPortList { 
	nodes { ap_memory {  { nodes_address0 mem_address 1 8 }  { nodes_ce0 mem_ce 1 1 }  { nodes_q0 in_data 0 128 } } }
	edges_0 { ap_memory {  { edges_0_address0 mem_address 1 10 }  { edges_0_ce0 mem_ce 1 1 }  { edges_0_q0 in_data 0 128 } } }
	edges_1 { ap_memory {  { edges_1_address0 mem_address 1 10 }  { edges_1_ce0 mem_ce 1 1 }  { edges_1_q0 in_data 0 128 } } }
	starting_node { ap_none {  { starting_node in_data 0 64 } } }
	level_0 { ap_memory {  { level_0_address0 mem_address 1 7 }  { level_0_ce0 mem_ce 1 1 }  { level_0_we0 mem_we 1 1 }  { level_0_d0 mem_din 1 8 }  { level_0_q0 in_data 0 8 } } }
	level_1 { ap_memory {  { level_1_address0 mem_address 1 7 }  { level_1_ce0 mem_ce 1 1 }  { level_1_we0 mem_we 1 1 }  { level_1_d0 mem_din 1 8 }  { level_1_q0 in_data 0 8 } } }
	level_counts { ap_memory {  { level_counts_address0 mem_address 1 4 }  { level_counts_ce0 mem_ce 1 1 }  { level_counts_we0 mem_we 1 1 }  { level_counts_d0 mem_din 1 64 } } }
}

set maxi_interface_dict [dict create]

# RTL port scheduling information:
set fifoSchedulingInfoList { 
}

# RTL bus port read request latency information:
set busReadReqLatencyList { 
}

# RTL bus port write response latency information:
set busWriteResLatencyList { 
}

# RTL array port load latency information:
set memoryLoadLatencyList { 
}
