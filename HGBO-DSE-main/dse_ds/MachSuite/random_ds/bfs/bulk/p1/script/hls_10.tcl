cd /home/noel/Documents/HGBO-DSE-main/benchmark/MachSuite/bfs/bulk
open_project bfs_random_prj_p1
add_files bfs.c
add_files local_support.c
set_top bfs
open_solution -reset solution
set_part xc7vx485tffg1761-2
create_clock -period 10
source /home/noel/Documents/HGBO-DSE-main/dse_ds/MachSuite/random_ds/bfs/bulk/p1/script/dir_10.tcl
csynth_design
exit
