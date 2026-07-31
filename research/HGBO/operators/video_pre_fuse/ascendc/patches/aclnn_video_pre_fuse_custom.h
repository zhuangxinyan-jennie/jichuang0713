
/*
 * calution: this file was generated automaticlly donot change it.
*/

#ifndef ACLNN_VIDEO_PRE_FUSE_CUSTOM_H_
#define ACLNN_VIDEO_PRE_FUSE_CUSTOM_H_

#include "aclnn/acl_meta.h"

#ifdef __cplusplus
extern "C" {
#endif

/* funtion: aclnnVideoPreFuseCustomGetWorkspaceSize
 * parameters :
 * x : required
 * y : required
 * workspaceSize : size of workspace(output).
 * executor : executor context(output).
 */
__attribute__((visibility("default")))
aclnnStatus aclnnVideoPreFuseCustomGetWorkspaceSize(
    const aclTensor *x,
    const aclTensor *y,
    uint64_t *workspaceSize,
    aclOpExecutor **executor);

/* funtion: aclnnVideoPreFuseCustom
 * parameters :
 * workspace : workspace memory addr(input).
 * workspaceSize : size of workspace(input).
 * executor : executor context(input).
 * stream : acl stream.
 */
__attribute__((visibility("default")))
aclnnStatus aclnnVideoPreFuseCustom(
    void *workspace,
    uint64_t workspaceSize,
    aclOpExecutor *executor,
    const aclrtStream stream);

#ifdef __cplusplus
}
#endif

#endif
