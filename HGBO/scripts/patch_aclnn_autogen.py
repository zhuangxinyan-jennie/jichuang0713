"""Patch broken aclnn autogen on board."""
from pathlib import Path

AUTOGEN = Path(
    "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/build_out/autogen/aclnn_video_pre_fuse_custom.cpp"
)

PATCH_OLD = """uint32_t socSupportList[] = {TensorDesc inputDesc0_0[1] =
    {{ge::DT_FLOAT16, ge::FORMAT_ND}};
TensorDesc outputDesc0_0[1] =
    {{ge::DT_FLOAT16, ge::FORMAT_ND}};
SupportInfo list0_0 = {inputDesc0_0, 1, outputDesc0_0, 1};
SupportInfo supportInfo0[1] = {list0_0};
OpSocSupportInfo socSupportInfo0= {supportInfo0, 1};

OpSocSupportInfo opSocSupportList[1] = {socSupportInfo0};
OpSupportList supportList = {opSocSupportList, 1};"""

PATCH_NEW = """TensorDesc inputDesc0_0[1] = {{ge::DT_FLOAT16, ge::FORMAT_ND}};
TensorDesc outputDesc0_0[1] = {{ge::DT_FLOAT16, ge::FORMAT_ND}};
SupportInfo list0_0 = {inputDesc0_0, 1, outputDesc0_0, 1};
SupportInfo supportInfo0[1] = {list0_0};
OpSocSupportInfo socSupportInfo0 = {supportInfo0, 1};
uint32_t socSupportList[] = {SOC_VERSION_ASCEND310B};
constexpr size_t socSupportListLen = sizeof(socSupportList) / sizeof(uint32_t);
OpSocSupportInfo opSocSupportList[1] = {socSupportInfo0};
OpSupportList supportList = {opSocSupportList, 1};"""


def main() -> None:
    text = AUTOGEN.read_text(encoding="utf-8")
    if PATCH_OLD not in text:
        raise SystemExit("patch pattern missing")
    AUTOGEN.write_text(text.replace(PATCH_OLD, PATCH_NEW, 1), encoding="utf-8")
    print("patched", AUTOGEN)


if __name__ == "__main__":
    main()
